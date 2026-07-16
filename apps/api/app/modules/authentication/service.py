from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    hash_opaque_token,
    hash_password,
    new_opaque_token,
    password_needs_rehash,
    utc_now,
    verify_password,
)
from app.modules.authentication.models import (
    AuthAttempt,
    AuthSession,
    CompanyInvitation,
    PasswordResetToken,
)
from app.modules.companies.models import Company
from app.modules.users.models import CompanyUser, User

logger = get_logger(component="authentication")


class InvalidCredentialsError(ValueError):
    pass


class LoginRateLimitedError(ValueError):
    pass


class InvalidRefreshTokenError(ValueError):
    pass


class InvalidOneTimeTokenError(ValueError):
    pass


class CompanyAccessError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    access_token: str
    access_expires_at: datetime
    refresh_token: str


class AuthenticationService:
    def __init__(self, database: AsyncSession, redis: Redis, settings: Settings) -> None:
        self.database = database
        self.redis = redis
        self.settings = settings

    def _rate_key(self, email: str, ip_address: str) -> str:
        fingerprint = sha256(f"{email.lower()}|{ip_address}".encode()).hexdigest()
        return f"auth:login:{fingerprint}"

    async def _check_rate_limit(self, email: str, ip_address: str) -> None:
        key = self._rate_key(email, ip_address)
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, self.settings.login_window_seconds)
        if count > self.settings.login_max_attempts:
            raise LoginRateLimitedError

    async def _record_attempt(
        self, *, email: str, ip_address: str, succeeded: bool, reason: str
    ) -> None:
        self.database.add(
            AuthAttempt(
                email=email.lower(),
                ip_address=ip_address,
                succeeded=succeeded,
                reason=reason,
            )
        )

    async def _active_memberships(self, user_id: UUID) -> list[tuple[CompanyUser, Company]]:
        rows = (
            await self.database.execute(
                select(CompanyUser, Company)
                .join(Company, Company.id == CompanyUser.company_id)
                .where(
                    CompanyUser.user_id == user_id,
                    CompanyUser.status == "active",
                    Company.status.in_(("active", "trial")),
                    Company.deleted_at.is_(None),
                )
                .order_by(Company.trade_name)
            )
        ).all()
        return [(membership, company) for membership, company in rows]

    def _issue_access(self, session: AuthSession) -> IssuedTokens:
        access_token, access_expires_at = create_access_token(
            self.settings,
            user_id=session.user_id,
            session_id=session.id,
            company_id=session.selected_company_id,
        )
        return IssuedTokens(
            access_token=access_token,
            access_expires_at=access_expires_at,
            refresh_token="",
        )

    async def login(
        self, *, email: str, password: str, ip_address: str, user_agent: str | None
    ) -> IssuedTokens:
        normalized_email = email.strip().lower()
        try:
            await self._check_rate_limit(normalized_email, ip_address)
        except LoginRateLimitedError:
            await self._record_attempt(
                email=normalized_email,
                ip_address=ip_address,
                succeeded=False,
                reason="rate_limited",
            )
            await self.database.commit()
            logger.warning("login_rate_limited", ip_address=ip_address)
            raise

        user = await self.database.scalar(
            select(User).where(User.email == normalized_email, User.deleted_at.is_(None))
        )
        if (
            user is None
            or user.status != "active"
            or not verify_password(user.password_hash, password)
        ):
            await self._record_attempt(
                email=normalized_email,
                ip_address=ip_address,
                succeeded=False,
                reason="invalid_credentials",
            )
            await self.database.commit()
            logger.warning("login_failed", ip_address=ip_address)
            raise InvalidCredentialsError

        if user.password_hash and password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        memberships = await self._active_memberships(user.id)
        selected_company_id = memberships[0][1].id if len(memberships) == 1 else None
        refresh_token = new_opaque_token()
        now = utc_now()
        auth_session = AuthSession(
            user_id=user.id,
            selected_company_id=selected_company_id,
            refresh_token_hash=hash_opaque_token(self.settings, refresh_token),
            ip_address=ip_address,
            user_agent=user_agent[:512] if user_agent else None,
            expires_at=now + timedelta(days=self.settings.refresh_token_days),
            last_used_at=now,
        )
        self.database.add(auth_session)
        user.last_login_at = now
        await self._record_attempt(
            email=normalized_email,
            ip_address=ip_address,
            succeeded=True,
            reason="success",
        )
        await self.database.commit()
        await self.redis.delete(self._rate_key(normalized_email, ip_address))
        issued = self._issue_access(auth_session)
        return IssuedTokens(issued.access_token, issued.access_expires_at, refresh_token)

    async def refresh(self, refresh_token: str) -> IssuedTokens:
        now = utc_now()
        token_hash = hash_opaque_token(self.settings, refresh_token)
        auth_session = await self.database.scalar(
            select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
        )
        if (
            auth_session is None
            or auth_session.revoked_at is not None
            or auth_session.expires_at <= now
        ):
            logger.warning("refresh_rejected")
            raise InvalidRefreshTokenError
        user = await self.database.scalar(
            select(User).where(
                User.id == auth_session.user_id,
                User.status == "active",
                User.deleted_at.is_(None),
            )
        )
        if user is None:
            auth_session.revoked_at = now
            await self.database.commit()
            raise InvalidRefreshTokenError

        if auth_session.selected_company_id is not None:
            membership = await self.database.scalar(
                select(CompanyUser)
                .join(Company, Company.id == CompanyUser.company_id)
                .where(
                    CompanyUser.user_id == user.id,
                    CompanyUser.company_id == auth_session.selected_company_id,
                    CompanyUser.status == "active",
                    Company.status.in_(("active", "trial")),
                    Company.deleted_at.is_(None),
                )
            )
            if membership is None:
                auth_session.selected_company_id = None

        rotated_refresh = new_opaque_token()
        auth_session.refresh_token_hash = hash_opaque_token(self.settings, rotated_refresh)
        auth_session.last_used_at = now
        await self.database.commit()
        issued = self._issue_access(auth_session)
        return IssuedTokens(issued.access_token, issued.access_expires_at, rotated_refresh)

    async def logout(self, refresh_token: str | None) -> None:
        if refresh_token:
            token_hash = hash_opaque_token(self.settings, refresh_token)
            auth_session = await self.database.scalar(
                select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
            )
            if auth_session is not None and auth_session.revoked_at is None:
                auth_session.revoked_at = utc_now()
                await self.database.commit()

    async def select_company(
        self, *, auth_session: AuthSession, user: User, company_id: UUID
    ) -> IssuedTokens:
        membership = await self.database.scalar(
            select(CompanyUser)
            .join(Company, Company.id == CompanyUser.company_id)
            .where(
                CompanyUser.user_id == user.id,
                CompanyUser.company_id == company_id,
                CompanyUser.status == "active",
                Company.status.in_(("active", "trial")),
                Company.deleted_at.is_(None),
            )
        )
        if membership is None:
            raise CompanyAccessError
        auth_session.selected_company_id = membership.company_id
        auth_session.last_used_at = utc_now()
        await self.database.commit()
        return self._issue_access(auth_session)

    async def forgot_password(self, *, email: str, ip_address: str) -> str | None:
        user = await self.database.scalar(
            select(User).where(
                User.email == email.strip().lower(),
                User.status == "active",
                User.deleted_at.is_(None),
            )
        )
        if user is None:
            return None
        now = utc_now()
        await self.database.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
            .values(used_at=now)
        )
        token = new_opaque_token()
        self.database.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_opaque_token(self.settings, token),
                requested_ip=ip_address,
                expires_at=now + timedelta(minutes=self.settings.password_reset_minutes),
            )
        )
        await self.database.commit()
        logger.info("password_reset_requested", user_id=str(user.id))
        return token

    async def reset_password(self, *, token: str, password: str) -> None:
        now = utc_now()
        reset_token = await self.database.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == hash_opaque_token(self.settings, token),
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
        )
        if reset_token is None:
            raise InvalidOneTimeTokenError
        user = await self.database.get(User, reset_token.user_id)
        if user is None or user.deleted_at is not None:
            raise InvalidOneTimeTokenError
        user.password_hash = hash_password(password)
        user.status = "active"
        reset_token.used_at = now
        await self.database.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self.database.commit()

    async def accept_invitation(self, *, token: str, name: str, password: str) -> None:
        now = utc_now()
        invitation = await self.database.scalar(
            select(CompanyInvitation).where(
                CompanyInvitation.token_hash == hash_opaque_token(self.settings, token),
                CompanyInvitation.accepted_at.is_(None),
                CompanyInvitation.revoked_at.is_(None),
                CompanyInvitation.expires_at > now,
            )
        )
        if invitation is None:
            raise InvalidOneTimeTokenError
        user = await self.database.get(User, invitation.user_id)
        membership = await self.database.scalar(
            select(CompanyUser).where(
                CompanyUser.user_id == invitation.user_id,
                CompanyUser.company_id == invitation.company_id,
            )
        )
        if user is None or membership is None:
            raise InvalidOneTimeTokenError
        user.name = name.strip()
        user.password_hash = hash_password(password)
        user.status = "active"
        membership.status = "active"
        invitation.accepted_at = now
        await self.database.commit()
