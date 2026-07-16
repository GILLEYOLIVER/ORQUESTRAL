from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, update

from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.security import hash_opaque_token, new_opaque_token, utc_now
from app.core.tenancy import CompanyOwnerContext
from app.modules.authentication.models import CompanyInvitation
from app.modules.users.models import CompanyUser, User
from app.modules.users.schemas import (
    CompanyUserResponse,
    CompanyUserUpdate,
    InvitationCreate,
    InvitationResponse,
)

router = APIRouter(prefix="/company", tags=["company-users"])


@router.get("/users", response_model=list[CompanyUserResponse])
async def list_company_users(
    context: CompanyOwnerContext,
    database: DatabaseSession,
) -> list[CompanyUserResponse]:
    rows = (
        await database.execute(
            select(CompanyUser, User)
            .join(User, User.id == CompanyUser.user_id)
            .where(CompanyUser.company_id == context.company_id, User.deleted_at.is_(None))
            .order_by(User.name)
        )
    ).all()
    return [
        CompanyUserResponse(
            membership_id=membership.id,
            user_id=user.id,
            name=user.name,
            email=user.email,
            user_status=user.status,
            membership_status=membership.status,
            role_id=membership.role_id,
            is_owner=membership.is_owner,
            created_at=membership.created_at,
        )
        for membership, user in rows
    ]


@router.post("/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def invite_company_user(
    payload: InvitationCreate,
    context: CompanyOwnerContext,
    database: DatabaseSession,
    settings: RequestSettings,
) -> InvitationResponse:
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
            status="invited",
        )
        database.add(membership)
    else:
        membership.status = "invited"

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
    context: CompanyOwnerContext,
    database: DatabaseSession,
) -> CompanyUserResponse:
    row = (
        await database.execute(
            select(CompanyUser, User)
            .join(User, User.id == CompanyUser.user_id)
            .where(
                CompanyUser.company_id == context.company_id,
                CompanyUser.user_id == user_id,
                User.deleted_at.is_(None),
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado na empresa.")
    membership, user = row
    if membership.is_owner and payload.status == "disabled":
        raise HTTPException(status_code=409, detail="O proprietário não pode ser desabilitado.")
    membership.status = payload.status
    await database.commit()
    return CompanyUserResponse(
        membership_id=membership.id,
        user_id=user.id,
        name=user.name,
        email=user.email,
        user_status=user.status,
        membership_status=membership.status,
        role_id=membership.role_id,
        is_owner=membership.is_owner,
        created_at=membership.created_at,
    )
