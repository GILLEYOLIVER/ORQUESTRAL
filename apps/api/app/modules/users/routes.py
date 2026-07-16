from __future__ import annotations

from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update

from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.security import hash_opaque_token, new_opaque_token, utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authentication.models import CompanyInvitation
from app.modules.authorization.catalog import SYSTEM_OWNER_ROLE_NAME
from app.modules.authorization.models import Role
from app.modules.authorization.service import record_authorization_audit
from app.modules.users.models import CompanyUser, User
from app.modules.users.schemas import (
    CompanyUserResponse,
    CompanyUserUpdate,
    InvitationCreate,
    InvitationResponse,
)

router = APIRouter(prefix="/company", tags=["company-users"])

CanViewUsers = Annotated[Principal, Depends(require_permission("users.view"))]
CanCreateUsers = Annotated[Principal, Depends(require_permission("users.create"))]
CanUpdateUsers = Annotated[Principal, Depends(require_permission("users.update"))]


def _member_response(membership: CompanyUser, user: User, role: Role | None) -> CompanyUserResponse:
    return CompanyUserResponse(
        membership_id=membership.id,
        user_id=user.id,
        name=user.name,
        email=user.email,
        user_status=user.status,
        membership_status=membership.status,
        role_id=membership.role_id,
        role_name=role.name if role else None,
        is_owner=membership.is_owner,
        created_at=membership.created_at,
    )


@router.get("/users", response_model=list[CompanyUserResponse])
async def list_company_users(
    principal: CanViewUsers,
    database: DatabaseSession,
) -> list[CompanyUserResponse]:
    context = get_request_context(principal)
    rows = (
        await database.execute(
            select(CompanyUser, User, Role)
            .join(User, User.id == CompanyUser.user_id)
            .outerjoin(Role, Role.id == CompanyUser.role_id)
            .where(CompanyUser.company_id == context.company_id, User.deleted_at.is_(None))
            .order_by(User.name)
        )
    ).all()
    return [_member_response(membership, user, role) for membership, user, role in rows]


@router.post("/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def invite_company_user(
    payload: InvitationCreate,
    principal: CanCreateUsers,
    database: DatabaseSession,
    settings: RequestSettings,
) -> InvitationResponse:
    context = get_request_context(principal)
    role = await database.scalar(
        select(Role).where(Role.id == payload.role_id, Role.company_id == context.company_id)
    )
    if role is None:
        raise HTTPException(status_code=422, detail="Papel inválido para a empresa atual.")
    if role.is_system_role and role.name.lower() == SYSTEM_OWNER_ROLE_NAME.lower():
        raise HTTPException(
            status_code=409, detail="O papel de proprietário não pode ser delegado."
        )

    email = str(payload.email).lower()
    user = await database.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is None:
        user = User(name=payload.name.strip(), email=email, status="invited")
        database.add(user)
        await database.flush()
    elif user.status == "disabled":
        raise HTTPException(status_code=409, detail="O usuário está desabilitado.")

    membership = await database.scalar(
        select(CompanyUser).where(
            CompanyUser.company_id == context.company_id,
            CompanyUser.user_id == user.id,
        )
    )
    if membership is not None and membership.status == "active":
        raise HTTPException(status_code=409, detail="O usuário já pertence à empresa.")
    if membership is None:
        membership = CompanyUser(
            company_id=context.company_id,
            user_id=user.id,
            role_id=role.id,
            status="invited",
        )
        database.add(membership)
    else:
        membership.status = "invited"
        membership.role_id = role.id

    now = utc_now()
    await database.execute(
        update(CompanyInvitation)
        .where(
            CompanyInvitation.company_id == context.company_id,
            CompanyInvitation.user_id == user.id,
            CompanyInvitation.accepted_at.is_(None),
            CompanyInvitation.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    token = new_opaque_token()
    invitation = CompanyInvitation(
        company_id=context.company_id,
        user_id=user.id,
        invited_by_user_id=context.user_id,
        token_hash=hash_opaque_token(settings, token),
        expires_at=now + timedelta(days=settings.invitation_days),
    )
    database.add(invitation)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="user.invited",
        target_type="user",
        target_id=user.id,
        details={"role_id": str(role.id)},
    )
    await database.commit()
    return InvitationResponse(
        id=invitation.id,
        email=user.email,
        expires_at=invitation.expires_at,
        development_token=token if settings.development_expose_tokens else None,
    )


@router.patch("/users/{user_id}", response_model=CompanyUserResponse)
async def update_company_user(
    user_id: UUID,
    payload: CompanyUserUpdate,
    principal: CanUpdateUsers,
    database: DatabaseSession,
) -> CompanyUserResponse:
    context = get_request_context(principal)
    row = (
        await database.execute(
            select(CompanyUser, User, Role)
            .join(User, User.id == CompanyUser.user_id)
            .outerjoin(Role, Role.id == CompanyUser.role_id)
            .where(
                CompanyUser.company_id == context.company_id,
                CompanyUser.user_id == user_id,
                User.deleted_at.is_(None),
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado na empresa.")
    membership, user, role = row
    if membership.is_owner:
        raise HTTPException(
            status_code=409, detail="O vínculo do proprietário não pode ser alterado."
        )

    if payload.role_id is not None:
        role = await database.scalar(
            select(Role).where(
                Role.id == payload.role_id,
                Role.company_id == context.company_id,
            )
        )
        if role is None:
            raise HTTPException(status_code=422, detail="Papel inválido para a empresa atual.")
        if role.is_system_role and role.name.lower() == SYSTEM_OWNER_ROLE_NAME.lower():
            raise HTTPException(
                status_code=409, detail="O papel de proprietário não pode ser delegado."
            )
        membership.role_id = role.id
    if payload.status is not None:
        membership.status = payload.status
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="user.membership_updated",
        target_type="user",
        target_id=user.id,
        details={
            "fields": sorted(payload.model_fields_set),
            "role_id": str(membership.role_id) if membership.role_id else None,
            "status": membership.status,
        },
    )
    await database.commit()
    return _member_response(membership, user, role)
