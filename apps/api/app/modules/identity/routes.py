from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import apply_tenant_database_context
from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.catalog import SYSTEM_OWNER_ROLE_NAME
from app.modules.authorization.models import Role
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.identity.models import EnterpriseIdentityProvider, SCIMProvisioningToken
from app.modules.identity.schemas import (
    IdentityProviderCreate,
    IdentityProviderResponse,
    SCIMListResponse,
    SCIMTokenCreate,
    SCIMTokenCreated,
    SCIMTokenResponse,
    SCIMUserCreate,
    SCIMUserPatch,
    SCIMUserResponse,
)
from app.modules.identity.service import (
    create_scim_token,
    parse_scim_token,
    scim_token_hash,
)
from app.modules.plugins.crypto import CredentialVault
from app.modules.users.models import CompanyUser, User

router = APIRouter(prefix="/identity", tags=["enterprise-identity"])
scim_router = APIRouter(prefix="/scim/v2", tags=["scim"])
CanView = Annotated[Principal, Depends(require_permission("identity.view"))]
CanManage = Annotated[Principal, Depends(require_permission("identity.manage"))]


def _provider_response(row: EnterpriseIdentityProvider) -> IdentityProviderResponse:
    return IdentityProviderResponse(
        id=row.id,
        code=row.code,
        name=row.name,
        provider_type=row.provider_type,
        issuer=row.issuer,
        client_id=row.client_id,
        client_secret_configured=row.encrypted_client_secret is not None,
        authorization_endpoint=row.authorization_endpoint,
        token_endpoint=row.token_endpoint,
        jwks_uri=row.jwks_uri,
        metadata_url=row.metadata_url,
        allowed_domains=row.allowed_domains,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/providers", response_model=list[IdentityProviderResponse])
async def list_identity_providers(
    principal: CanView, database: DatabaseSession
) -> list[IdentityProviderResponse]:
    context = get_request_context(principal)
    rows = await database.scalars(
        select(EnterpriseIdentityProvider)
        .where(EnterpriseIdentityProvider.company_id == context.company_id)
        .order_by(EnterpriseIdentityProvider.name)
    )
    return [_provider_response(row) for row in rows]


@router.post("/providers", response_model=IdentityProviderResponse, status_code=201)
async def create_identity_provider(
    payload: IdentityProviderCreate,
    principal: CanManage,
    database: DatabaseSession,
    settings: RequestSettings,
) -> IdentityProviderResponse:
    context = get_request_context(principal)
    secret = (
        CredentialVault(settings.encryption_key).encrypt({"client_secret": payload.client_secret})
        if payload.client_secret
        else None
    )
    row = EnterpriseIdentityProvider(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        code=payload.code,
        name=payload.name,
        provider_type=payload.provider_type,
        issuer=str(payload.issuer),
        client_id=payload.client_id,
        encrypted_client_secret=secret,
        authorization_endpoint=(
            str(payload.authorization_endpoint) if payload.authorization_endpoint else None
        ),
        token_endpoint=str(payload.token_endpoint) if payload.token_endpoint else None,
        jwks_uri=str(payload.jwks_uri) if payload.jwks_uri else None,
        metadata_url=str(payload.metadata_url) if payload.metadata_url else None,
        allowed_domains=sorted({domain.lower().strip() for domain in payload.allowed_domains}),
    )
    database.add(row)
    try:
        await database.flush()
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="Código de provedor já utilizado.") from error
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="identity.provider.configured",
        target_type="enterprise_identity_provider",
        target_id=row.id,
        details={"code": row.code, "provider_type": row.provider_type},
    )
    await database.commit()
    await database.refresh(row)
    return _provider_response(row)


@router.get("/scim/tokens", response_model=list[SCIMTokenResponse])
async def list_scim_tokens(
    principal: CanView, database: DatabaseSession
) -> list[SCIMTokenResponse]:
    context = get_request_context(principal)
    rows = await database.scalars(
        select(SCIMProvisioningToken)
        .where(SCIMProvisioningToken.company_id == context.company_id)
        .order_by(SCIMProvisioningToken.created_at.desc())
    )
    return [SCIMTokenResponse.model_validate(row) for row in rows]


@router.post("/scim/tokens", response_model=SCIMTokenCreated, status_code=201)
async def create_scim_access_token(
    payload: SCIMTokenCreate,
    principal: CanManage,
    database: DatabaseSession,
    settings: RequestSettings,
) -> SCIMTokenCreated:
    context = get_request_context(principal)
    if payload.expires_at <= utc_now():
        raise HTTPException(status_code=422, detail="A expiração deve estar no futuro.")
    role = await database.scalar(
        select(Role).where(Role.id == payload.default_role_id, Role.company_id == context.company_id)
    )
    if role is None or (role.is_system_role and role.name.casefold() == SYSTEM_OWNER_ROLE_NAME.casefold()):
        raise HTTPException(status_code=422, detail="Papel padrão inválido para SCIM.")
    token_id = uuid4()
    raw_token = create_scim_token(context.company_id, token_id)
    row = SCIMProvisioningToken(
        id=token_id,
        company_id=context.company_id,
        name=payload.name,
        token_hash=scim_token_hash(settings, raw_token),
        scopes=sorted(set(payload.scopes)),
        default_role_id=role.id,
        expires_at=payload.expires_at,
        created_by_user_id=context.user_id,
    )
    database.add(row)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="identity.scim_token.created",
        target_type="scim_provisioning_token",
        target_id=row.id,
        details={"scopes": row.scopes, "expires_at": row.expires_at.isoformat()},
    )
    await database.commit()
    return SCIMTokenCreated(
        id=row.id,
        name=row.name,
        token=raw_token,
        scopes=row.scopes,
        expires_at=row.expires_at,
    )


@router.delete("/scim/tokens/{token_id}", status_code=204)
async def revoke_scim_access_token(
    token_id: UUID,
    principal: CanManage,
    database: DatabaseSession,
) -> None:
    context = get_request_context(principal)
    row = await database.scalar(
        select(SCIMProvisioningToken).where(
            SCIMProvisioningToken.id == token_id,
            SCIMProvisioningToken.company_id == context.company_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Token SCIM não encontrado.")
    row.status = "revoked"
    row.revoked_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="identity.scim_token.revoked",
        target_type="scim_provisioning_token",
        target_id=row.id,
    )
    await database.commit()


@dataclass(frozen=True, slots=True)
class SCIMContext:
    company_id: UUID
    actor_user_id: UUID
    scopes: frozenset[str]
    token_id: UUID


async def require_scim_access(
    database: DatabaseSession,
    settings: RequestSettings,
    authorization: Annotated[str | None, Header()] = None,
) -> SCIMContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token SCIM necessário.")
    raw_token = authorization.removeprefix("Bearer ").strip()
    try:
        parts = parse_scim_token(raw_token)
    except ValueError as error:
        raise HTTPException(status_code=401, detail="Token SCIM inválido.") from error
    await apply_tenant_database_context(
        database, company_id=parts.company_id, access_mode="standard"
    )
    row = await database.scalar(
        select(SCIMProvisioningToken).where(
            SCIMProvisioningToken.id == parts.token_id,
            SCIMProvisioningToken.company_id == parts.company_id,
            SCIMProvisioningToken.token_hash == scim_token_hash(settings, raw_token),
            SCIMProvisioningToken.status == "active",
        )
    )
    if row is None or row.expires_at <= utc_now():
        raise HTTPException(status_code=401, detail="Token SCIM inválido ou expirado.")
    row.last_used_at = utc_now()
    return SCIMContext(
        company_id=row.company_id,
        actor_user_id=row.created_by_user_id,
        scopes=frozenset(row.scopes),
        token_id=row.id,
    )


SCIMAccess = Annotated[SCIMContext, Depends(require_scim_access)]


def _require_scope(context: SCIMContext, scope: str) -> None:
    if scope not in context.scopes:
        raise HTTPException(status_code=403, detail="Escopo SCIM insuficiente.")


def _scim_user(user: User, membership: CompanyUser) -> SCIMUserResponse:
    return SCIMUserResponse(
        schemas=["urn:ietf:params:scim:schemas:core:2.0:User"],
        id=str(user.id),
        userName=user.email,
        displayName=user.name,
        active=membership.status == "active",
        meta={"resourceType": "User", "created": user.created_at.isoformat()},
    )


@scim_router.get("/Users", response_model=SCIMListResponse)
async def list_scim_users(
    context: SCIMAccess, database: DatabaseSession
) -> SCIMListResponse:
    _require_scope(context, "users.read")
    rows = (
        await database.execute(
            select(User, CompanyUser)
            .join(CompanyUser, CompanyUser.user_id == User.id)
            .where(
                CompanyUser.company_id == context.company_id,
                User.deleted_at.is_(None),
            )
            .order_by(User.email)
            .limit(200)
        )
    ).all()
    resources = [_scim_user(user, membership) for user, membership in rows]
    return SCIMListResponse(
        schemas=["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        totalResults=len(resources),
        startIndex=1,
        itemsPerPage=len(resources),
        Resources=resources,
    )


@scim_router.post("/Users", response_model=SCIMUserResponse, status_code=201)
async def provision_scim_user(
    payload: SCIMUserCreate,
    context: SCIMAccess,
    database: DatabaseSession,
) -> SCIMUserResponse:
    _require_scope(context, "users.write")
    token = await database.get(SCIMProvisioningToken, context.token_id)
    if token is None:
        raise HTTPException(status_code=401, detail="Token SCIM inválido.")
    email = str(payload.userName).casefold()
    user = await database.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is None:
        user = User(
            name=payload.displayName.strip(),
            email=email,
            password_hash=None,
            status="active" if payload.active else "disabled",
        )
        database.add(user)
        await database.flush()
    membership = await database.scalar(
        select(CompanyUser).where(
            CompanyUser.company_id == context.company_id,
            CompanyUser.user_id == user.id,
        )
    )
    if membership is None:
        membership = CompanyUser(
            company_id=context.company_id,
            user_id=user.id,
            role_id=token.default_role_id,
            status="active" if payload.active else "disabled",
        )
        database.add(membership)
    else:
        membership.status = "active" if payload.active else "disabled"
        membership.role_id = token.default_role_id
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.actor_user_id,
        action="identity.scim_user.provisioned",
        target_type="user",
        target_id=user.id,
        details={"active": payload.active, "token_id": str(context.token_id)},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="identity.scim_user.provisioned",
            company_id=context.company_id,
            actor_user_id=context.actor_user_id,
            classification="restricted",
            payload={"user_id": str(user.id), "active": payload.active},
        ),
    )
    await database.commit()
    await database.refresh(user)
    await database.refresh(membership)
    return _scim_user(user, membership)


@scim_router.patch("/Users/{user_id}", response_model=SCIMUserResponse)
async def patch_scim_user(
    user_id: UUID,
    payload: SCIMUserPatch,
    context: SCIMAccess,
    database: DatabaseSession,
) -> SCIMUserResponse:
    _require_scope(context, "users.write")
    row = (
        await database.execute(
            select(User, CompanyUser)
            .join(CompanyUser, CompanyUser.user_id == User.id)
            .where(
                User.id == user_id,
                CompanyUser.company_id == context.company_id,
                User.deleted_at.is_(None),
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Usuário SCIM não encontrado.")
    user, membership = row
    if membership.is_owner:
        raise HTTPException(status_code=409, detail="O proprietário não pode ser alterado por SCIM.")
    for operation in payload.Operations:
        membership.status = "active" if operation.value else "disabled"
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.actor_user_id,
        action="identity.scim_user.updated",
        target_type="user",
        target_id=user.id,
        details={"active": membership.status == "active", "token_id": str(context.token_id)},
    )
    await database.commit()
    await database.refresh(membership)
    return _scim_user(user, membership)
