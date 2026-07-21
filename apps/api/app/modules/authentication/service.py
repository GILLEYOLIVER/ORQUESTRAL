from __future__ import annotations

import json
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
    ReadOnlyAccessLink,
)
from app.modules.authorization.models import Permission, RolePermission
from app.modules.authorization.service import record_authorization_audit
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


class InvalidReadOnlyLinkError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    access_token: str
    access_expires_at: datetime
    refresh_token: str


@dataclass(frozen=True, slots=True)
class ReadOnlyLinkCandidate:
    company_id: UUID
    company_name: str
    user_id: UUID
    user_name: str
    user_email: str


@dataclass(frozen=True, slots=True)
class ReadOnlyLinkAuthorization:
    token: str
    expires_at: datetime
    candidates: tuple[ReadOnlyLinkCandidate, ...]


@dataclass(frozen=True, slots=True)
class IssuedReadOnlyLink:
    link: ReadOnlyAccessLink
    token: str


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
            access_mode=session.access_mode,
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

    def _read_only_authorization_key(self, token: str) -> str:
        return f"auth:read-only-link:{hash_opaque_token(self.settings, token)}"

    async def _read_only_candidates(
        self, company_ids: tuple[UUID, ...]
    ) -> tuple[ReadOnlyLinkCandidate, ...]:
        rows = (
            await self.database.execute(
                select(CompanyUser, User, Company)
                .join(User, User.id == CompanyUser.user_id)
                .join(Company, Company.id == CompanyUser.company_id)
                .where(
                    CompanyUser.company_id.in_(company_ids),
                    CompanyUser.status == "active",
                    User.status == "active",
                    User.deleted_at.is_(None),
                    Company.status.in_(("active", "trial")),
                    Company.deleted_at.is_(None),
                )
                .order_by(Company.trade_name, User.name)
            )
        ).all()
        return tuple(
            ReadOnlyLinkCandidate(
                company_id=company.id,
                company_name=company.trade_name,
                user_id=user.id,
                user_name=user.name,
                user_email=user.email,
            )
            for _, user, company in rows
        )

    async def authorize_read_only_link(
        self, *, email: str, password: str, ip_address: str
    ) -> ReadOnlyLinkAuthorization:
        normalized_email = email.strip().lower()
        try:
            await self._check_rate_limit(normalized_email, ip_address)
        except LoginRateLimitedError:
            await self._record_attempt(
                email=normalized_email,
                ip_address=ip_address,
                succeeded=False,
                reason="read_only_link_rate_limited",
            )
            await self.database.commit()
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
                reason="read_only_link_invalid_credentials",
            )
            await self.database.commit()
            raise InvalidCredentialsError

        memberships = await self._active_memberships(user.id)
        managed_role_ids = set(
            await self.database.scalars(
                select(RolePermission.role_id)
                .join(Permission, Permission.id == RolePermission.permission_id)
                .where(Permission.code == "access_links.manage")
            )
        )
        company_ids = tuple(
            company.id
            for membership, company in memberships
            if membership.is_owner
            or membership.role_id in managed_role_ids
            or user.is_platform_admin
        )
        if not company_ids:
            await self._record_attempt(
                email=normalized_email,
                ip_address=ip_address,
                succeeded=False,
                reason="read_only_link_forbidden",
            )
            await self.database.commit()
            raise CompanyAccessError

        token = new_opaque_token()
        expires_at = utc_now() + timedelta(
            minutes=self.settings.read_only_link_authorization_minutes
        )
        await self.redis.setex(
            self._read_only_authorization_key(token),
            self.settings.read_only_link_authorization_minutes * 60,
            json.dumps(
                {
                    "administrator_user_id": str(user.id),
                    "company_ids": [str(company_id) for company_id in company_ids],
                }
            ),
        )
        await self._record_attempt(
            email=normalized_email,
            ip_address=ip_address,
            succeeded=True,
            reason="read_only_link_authorized",
        )
        await self.database.commit()
        await self.redis.delete(self._rate_key(normalized_email, ip_address))
        return ReadOnlyLinkAuthorization(
            token=token,
            expires_at=expires_at,
            candidates=await self._read_only_candidates(company_ids),
        )

    async def _read_link_authorization(self, token: str) -> tuple[UUID, tuple[UUID, ...]]:
        encoded = await self.redis.get(self._read_only_authorization_key(token))
        if not encoded:
            raise InvalidReadOnlyLinkError
        try:
            payload = json.loads(encoded.decode() if isinstance(encoded, bytes) else encoded)
            administrator_user_id = UUID(str(payload["administrator_user_id"]))
            company_ids = tuple(UUID(str(value)) for value in payload["company_ids"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise InvalidReadOnlyLinkError from exc
        return administrator_user_id, company_ids

    async def create_read_only_link(
        self,
        *,
        authorization_token: str,
        company_id: UUID,
        target_user_id: UUID,
        expiration_minutes: int,
    ) -> IssuedReadOnlyLink:
        administrator_user_id, allowed_company_ids = await self._read_link_authorization(
            authorization_token
        )
        if (
            company_id not in allowed_company_ids
            or expiration_minutes > self.settings.read_only_link_max_days * 1_440
        ):
            raise CompanyAccessError
        membership = await self.database.scalar(
            select(CompanyUser)
            .join(User, User.id == CompanyUser.user_id)
            .join(Company, Company.id == CompanyUser.company_id)
            .where(
                CompanyUser.company_id == company_id,
                CompanyUser.user_id == target_user_id,
                CompanyUser.status == "active",
                User.status == "active",
                User.deleted_at.is_(None),
                Company.status.in_(("active", "trial")),
                Company.deleted_at.is_(None),
            )
        )
        if membership is None:
            raise CompanyAccessError
        raw_token = new_opaque_token()
        link = ReadOnlyAccessLink(
            company_id=company_id,
            target_user_id=target_user_id,
            created_by_user_id=administrator_user_id,
            token_hash=hash_opaque_token(self.settings, raw_token),
            expires_at=utc_now() + timedelta(minutes=expiration_minutes),
        )
        self.database.add(link)
        await self.database.flush()
        record_authorization_audit(
            self.database,
            company_id=company_id,
            actor_user_id=administrator_user_id,
            action="read_only_access_link.created",
            target_type="read_only_access_link",
            target_id=link.id,
            details={
                "target_user_id": str(target_user_id),
                "expires_at": link.expires_at.isoformat(),
            },
        )
        await self.database.commit()
        await self.redis.delete(self._read_only_authorization_key(authorization_token))
        return IssuedReadOnlyLink(link=link, token=raw_token)

    async def exchange_read_only_link(
        self, *, token: str, ip_address: str, user_agent: str | None
    ) -> IssuedTokens:
        now = utc_now()
        link = await self.database.scalar(
            select(ReadOnlyAccessLink)
            .where(ReadOnlyAccessLink.token_hash == hash_opaque_token(self.settings, token))
            .with_for_update()
        )
        if link is None or link.revoked_at is not None or link.expires_at <= now:
            raise InvalidReadOnlyLinkError
        row = (
            await self.database.execute(
                select(User, CompanyUser, Company)
                .join(CompanyUser, CompanyUser.user_id == User.id)
                .join(Company, Company.id == CompanyUser.company_id)
                .where(
                    User.id == link.target_user_id,
                    User.status == "active",
                    User.deleted_at.is_(None),
                    CompanyUser.company_id == link.company_id,
                    CompanyUser.status == "active",
                    Company.status.in_(("active", "trial")),
                    Company.deleted_at.is_(None),
                )
            )
        ).first()
        if row is None:
            raise InvalidReadOnlyLinkError
        user, _, _ = row
        refresh_token = new_opaque_token()
        auth_session = AuthSession(
            user_id=user.id,
            selected_company_id=link.company_id,
            access_mode="read_only",
            read_only_access_link_id=link.id,
            refresh_token_hash=hash_opaque_token(self.settings, refresh_token),
            ip_address=ip_address,
            user_agent=user_agent[:512] if user_agent else None,
            expires_at=min(
                link.expires_at,
                now + timedelta(days=self.settings.refresh_token_days),
            ),
            last_used_at=now,
        )
        self.database.add(auth_session)
        link.first_used_at = link.first_used_at or now
        link.last_used_at = now
        link.usage_count += 1
        record_authorization_audit(
            self.database,
            company_id=link.company_id,
            actor_user_id=user.id,
            action="read_only_access_link.used",
            target_type="read_only_access_link",
            target_id=link.id,
            details={"created_by_user_id": str(link.created_by_user_id)},
        )
        await self.database.commit()
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

    async def active_sessions(self, user_id: UUID) -> list[AuthSession]:
        now = utc_now()
        return list(
            await self.database.scalars(
                select(AuthSession)
                .where(
                    AuthSession.user_id == user_id,
                    AuthSession.revoked_at.is_(None),
                    AuthSession.expires_at > now,
                )
                .order_by(AuthSession.last_used_at.desc())
            )
        )

    async def revoke_session(self, *, user_id: UUID, session_id: UUID) -> bool:
        auth_session = await self.database.scalar(
            select(AuthSession).where(
                AuthSession.id == session_id,
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
        )
        if auth_session is None:
            return False
        auth_session.revoked_at = utc_now()
        await self.database.commit()
        return True

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
