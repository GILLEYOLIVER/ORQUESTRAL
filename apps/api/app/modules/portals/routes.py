from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import CurrentPrincipal, Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.portals.models import PortalDefinition, PortalInvitation, PortalMembership
from app.modules.portals.schemas import (
    PortalAccessResponse,
    PortalCreate,
    PortalInviteAccept,
    PortalInviteCreate,
    PortalInviteResponse,
    PortalResponse,
)
from app.modules.portals.service import create_invitation_token, hash_invitation_token

router = APIRouter(prefix="/portals", tags=["portals"])
CanViewPortals = Annotated[Principal, Depends(require_permission("portals.view"))]
CanManagePortals = Annotated[Principal, Depends(require_permission("portals.manage"))]


@router.get("", response_model=list[PortalResponse])
async def list_portals(
    principal: CanViewPortals, database: DatabaseSession
) -> list[PortalResponse]:
    context = get_request_context(principal)
    rows = list(
        await database.scalars(
            select(PortalDefinition)
            .where(PortalDefinition.company_id == context.company_id)
            .order_by(PortalDefinition.name)
        )
    )
    return [PortalResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("", response_model=PortalResponse, status_code=status.HTTP_201_CREATED)
async def create_portal(
    payload: PortalCreate,
    principal: CanManagePortals,
    database: DatabaseSession,
) -> PortalResponse:
    context = get_request_context(principal)
    portal = PortalDefinition(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **payload.model_dump(mode="json"),
    )
    database.add(portal)
    try:
        await database.flush()
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="Código de portal já utilizado.") from error
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="portal.created",
        target_type="portal_definition",
        target_id=portal.id,
    )
    await database.commit()
    await database.refresh(portal)
    return PortalResponse.model_validate(portal, from_attributes=True)


@router.post(
    "/{portal_code}/invitations",
    response_model=PortalInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    portal_code: str,
    payload: PortalInviteCreate,
    principal: CanManagePortals,
    database: DatabaseSession,
) -> PortalInviteResponse:
    context = get_request_context(principal)
    portal = await database.scalar(
        select(PortalDefinition).where(
            PortalDefinition.company_id == context.company_id,
            PortalDefinition.code == portal_code,
            PortalDefinition.active.is_(True),
        )
    )
    if not portal:
        raise HTTPException(status_code=404, detail="Portal não encontrado.")
    member = await database.scalar(
        text(
            "SELECT 1 FROM company_users WHERE company_id=:company_id "
            "AND user_id=:user_id AND status='active'"
        ),
        {"company_id": context.company_id, "user_id": payload.user_id},
    )
    if not member:
        raise HTTPException(status_code=422, detail="Usuário não pertence à empresa.")
    membership = await database.scalar(
        select(PortalMembership).where(
            PortalMembership.portal_id == portal.id,
            PortalMembership.user_id == payload.user_id,
            PortalMembership.company_id == context.company_id,
        )
    )
    if not membership:
        membership = PortalMembership(
            company_id=context.company_id,
            portal_id=portal.id,
            user_id=payload.user_id,
            status="invited",
            invited_by_user_id=context.user_id,
        )
        database.add(membership)
        await database.flush()
    token, token_hash = create_invitation_token()
    expires_at = utc_now() + timedelta(hours=payload.expiration_hours)
    invitation = PortalInvitation(
        company_id=context.company_id,
        membership_id=membership.id,
        token_hash=token_hash,
        expires_at=expires_at,
        created_by_user_id=context.user_id,
    )
    database.add(invitation)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="portal.invitation.created",
        target_type="portal_invitation",
        target_id=invitation.id,
        details={"membership_id": str(membership.id)},
    )
    await database.commit()
    return PortalInviteResponse(
        membership_id=membership.id,
        invitation_id=invitation.id,
        token=token,
        expires_at=expires_at,
    )


@router.post("/invitations/accept", status_code=status.HTTP_204_NO_CONTENT)
async def accept_invitation(
    payload: PortalInviteAccept,
    principal: CurrentPrincipal,
    database: DatabaseSession,
) -> None:
    context = get_request_context(principal)
    invitation = await database.scalar(
        select(PortalInvitation)
        .where(
            PortalInvitation.company_id == context.company_id,
            PortalInvitation.token_hash == hash_invitation_token(payload.token),
            PortalInvitation.accepted_at.is_(None),
            PortalInvitation.revoked_at.is_(None),
            PortalInvitation.expires_at > utc_now(),
        )
        .with_for_update()
    )
    if not invitation:
        raise HTTPException(status_code=404, detail="Convite inválido ou expirado.")
    membership = await database.scalar(
        select(PortalMembership).where(
            PortalMembership.id == invitation.membership_id,
            PortalMembership.company_id == context.company_id,
            PortalMembership.user_id == context.user_id,
        )
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Convite destinado a outro usuário.")
    invitation.accepted_at = utc_now()
    membership.status = "active"
    membership.activated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="portal.invitation.accepted",
        target_type="portal_membership",
        target_id=membership.id,
    )
    await database.commit()


@router.get("/{portal_code}/me", response_model=PortalAccessResponse)
async def portal_access(
    portal_code: str,
    principal: CurrentPrincipal,
    database: DatabaseSession,
) -> PortalAccessResponse:
    context = get_request_context(principal)
    row = (
        await database.execute(
            select(PortalDefinition, PortalMembership)
            .join(PortalMembership, PortalMembership.portal_id == PortalDefinition.id)
            .where(
                PortalDefinition.company_id == context.company_id,
                PortalDefinition.code == portal_code,
                PortalDefinition.active.is_(True),
                PortalMembership.company_id == context.company_id,
                PortalMembership.user_id == context.user_id,
                PortalMembership.status == "active",
            )
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Acesso ao portal não encontrado.")
    portal, membership = row
    return PortalAccessResponse(
        portal=PortalResponse.model_validate(portal, from_attributes=True),
        membership_status=membership.status,
    )
