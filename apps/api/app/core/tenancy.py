from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.security import InvalidAccessTokenError, decode_access_token, utc_now
from app.modules.authentication.models import AuthSession
from app.modules.authorization.catalog import PLATFORM_PERMISSION_CODES, TENANT_PERMISSION_CODES
from app.modules.authorization.models import Permission, RolePermission
from app.modules.companies.models import Company
from app.modules.users.models import CompanyUser, User

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class Principal:
    user: User
    session: AuthSession
    company: Company | None
    membership: CompanyUser | None
    permissions: frozenset[str]


@dataclass(frozen=True, slots=True)
class RequestContext:
    user_id: UUID
    company_id: UUID
    role_ids: tuple[UUID, ...]
    permissions: frozenset[str]
    is_owner: bool
    is_platform_admin: bool


async def get_current_principal(
    database: DatabaseSession,
    settings: RequestSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Autenticação necessária.")
    try:
        claims = decode_access_token(settings, credentials.credentials)
    except InvalidAccessTokenError as exc:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.") from exc

    user = await database.scalar(
        select(User).where(
            User.id == claims.user_id,
            User.status == "active",
            User.deleted_at.is_(None),
        )
    )
    session = await database.scalar(
        select(AuthSession).where(
            AuthSession.id == claims.session_id,
            AuthSession.user_id == claims.user_id,
        )
    )
    now = utc_now()
    if (
        user is None
        or session is None
        or session.revoked_at is not None
        or session.expires_at <= now
        or session.selected_company_id != claims.company_id
        or session.access_mode != claims.access_mode
    ):
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")

    company: Company | None = None
    membership: CompanyUser | None = None
    permissions: set[str] = set()
    if user.is_platform_admin:
        permissions.update(PLATFORM_PERMISSION_CODES)
    if claims.company_id is not None:
        row = (
            await database.execute(
                select(CompanyUser, Company)
                .join(Company, Company.id == CompanyUser.company_id)
                .where(
                    CompanyUser.user_id == user.id,
                    CompanyUser.company_id == claims.company_id,
                    CompanyUser.status == "active",
                    Company.status.in_(("active", "trial")),
                    Company.deleted_at.is_(None),
                )
            )
        ).first()
        if row is None:
            if not user.is_platform_admin:
                raise HTTPException(status_code=403, detail="Acesso à empresa não autorizado.")
        else:
            membership, company = row
            if session.access_mode == "read_only":
                permissions.update(TENANT_PERMISSION_CODES)
            elif membership.is_owner:
                permissions.update(TENANT_PERMISSION_CODES)
            elif membership.role_id is not None:
                permissions.update(
                    await database.scalars(
                        select(Permission.code)
                        .join(
                            RolePermission,
                            RolePermission.permission_id == Permission.id,
                        )
                        .where(RolePermission.role_id == membership.role_id)
                    )
                )

    return Principal(
        user=user,
        session=session,
        company=company,
        membership=membership,
        permissions=frozenset(permissions),
    )


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def require_platform_admin(principal: CurrentPrincipal) -> Principal:
    if not principal.user.is_platform_admin:
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito à administração da plataforma.",
        )
    return principal


PlatformAdmin = Annotated[Principal, Depends(require_platform_admin)]


def get_request_context(principal: CurrentPrincipal) -> RequestContext:
    if principal.company is None or principal.membership is None:
        raise HTTPException(status_code=409, detail="Selecione uma empresa para continuar.")
    role_ids = (principal.membership.role_id,) if principal.membership.role_id else ()
    return RequestContext(
        user_id=principal.user.id,
        company_id=principal.company.id,
        role_ids=role_ids,
        permissions=principal.permissions,
        is_owner=principal.membership.is_owner,
        is_platform_admin=principal.user.is_platform_admin,
    )


CurrentRequestContext = Annotated[RequestContext, Depends(get_request_context)]


def require_company_owner(context: CurrentRequestContext) -> RequestContext:
    if not context.is_owner:
        raise HTTPException(status_code=403, detail="Acesso restrito ao proprietário da empresa.")
    return context


CompanyOwnerContext = Annotated[RequestContext, Depends(require_company_owner)]


def require_permission(
    permission_code: str,
) -> Callable[[CurrentPrincipal], Coroutine[Any, Any, Principal]]:
    async def permission_dependency(principal: CurrentPrincipal) -> Principal:
        if permission_code not in principal.permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Permissão necessária: {permission_code}.",
            )
        return principal

    return permission_dependency
