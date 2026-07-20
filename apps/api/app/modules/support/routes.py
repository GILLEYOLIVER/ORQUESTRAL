from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.crm.models import CRMContact
from app.modules.modularity.dependencies import require_active_module
from app.modules.support.models import SupportInteraction, SupportTicket
from app.modules.support.schemas import (
    SupportInteractionCreate,
    SupportInteractionResponse,
    SupportTicketCreate,
    SupportTicketResponse,
    SupportTicketUpdate,
    TicketPriority,
    TicketStatus,
)
from app.modules.users.models import CompanyUser

router = APIRouter(prefix="/support", tags=["support"])

ActiveSupport = Annotated[Principal, Depends(require_active_module("support"))]
CanViewTickets = Annotated[Principal, Depends(require_permission("support.tickets.view"))]
CanCreateTickets = Annotated[Principal, Depends(require_permission("support.tickets.create"))]
CanUpdateTickets = Annotated[Principal, Depends(require_permission("support.tickets.update"))]
CanCommentTickets = Annotated[Principal, Depends(require_permission("support.tickets.comment"))]


async def _ticket(database: DatabaseSession, company_id: UUID, ticket_id: UUID) -> SupportTicket:
    ticket = await database.scalar(
        select(SupportTicket).where(
            SupportTicket.id == ticket_id,
            SupportTicket.company_id == company_id,
        )
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail="Chamado nao encontrado.")
    return ticket


async def _validate_assignee(
    database: DatabaseSession, company_id: UUID, user_id: UUID | None
) -> None:
    if user_id is None:
        return
    membership = await database.scalar(
        select(CompanyUser.id).where(
            CompanyUser.company_id == company_id,
            CompanyUser.user_id == user_id,
            CompanyUser.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=422, detail="Responsavel invalido para a empresa atual.")


async def _validate_requester(
    database: DatabaseSession, company_id: UUID, contact_id: UUID | None
) -> None:
    if contact_id is None:
        return
    contact = await database.scalar(
        select(CRMContact.id).where(
            CRMContact.id == contact_id,
            CRMContact.company_id == company_id,
            CRMContact.deleted_at.is_(None),
        )
    )
    if contact is None:
        raise HTTPException(status_code=422, detail="Contato solicitante invalido.")


def _ticket_response(ticket: SupportTicket) -> SupportTicketResponse:
    return SupportTicketResponse.model_validate(ticket, from_attributes=True)


@router.get("/tickets", response_model=list[SupportTicketResponse])
async def list_tickets(
    principal: CanViewTickets,
    _: ActiveSupport,
    database: DatabaseSession,
    search: str | None = Query(default=None, max_length=120),
    ticket_status: TicketStatus | None = Query(default=None, alias="status"),
    priority: TicketPriority | None = Query(default=None),
) -> list[SupportTicketResponse]:
    context = get_request_context(principal)
    statement = select(SupportTicket).where(SupportTicket.company_id == context.company_id)
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(SupportTicket.subject.ilike(term), SupportTicket.description.ilike(term))
        )
    if ticket_status:
        statement = statement.where(SupportTicket.status == ticket_status)
    if priority:
        statement = statement.where(SupportTicket.priority == priority)
    tickets = list(
        await database.scalars(statement.order_by(SupportTicket.created_at.desc()).limit(200))
    )
    return [_ticket_response(ticket) for ticket in tickets]


@router.post("/tickets", response_model=SupportTicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: SupportTicketCreate,
    principal: CanCreateTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportTicketResponse:
    context = get_request_context(principal)
    await _validate_assignee(database, context.company_id, payload.assignee_user_id)
    await _validate_requester(database, context.company_id, payload.requester_contact_id)
    ticket = SupportTicket(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    database.add(ticket)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="support.ticket.created",
        target_type="support_ticket",
        target_id=ticket.id,
        details={"priority": ticket.priority, "channel": ticket.channel},
    )
    await database.commit()
    await database.refresh(ticket)
    return _ticket_response(ticket)


@router.get("/tickets/{ticket_id}", response_model=SupportTicketResponse)
async def get_ticket(
    ticket_id: UUID,
    principal: CanViewTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportTicketResponse:
    context = get_request_context(principal)
    return _ticket_response(await _ticket(database, context.company_id, ticket_id))


@router.patch("/tickets/{ticket_id}", response_model=SupportTicketResponse)
async def update_ticket(
    ticket_id: UUID,
    payload: SupportTicketUpdate,
    principal: CanUpdateTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportTicketResponse:
    context = get_request_context(principal)
    ticket = await _ticket(database, context.company_id, ticket_id)
    if "assignee_user_id" in payload.model_fields_set:
        await _validate_assignee(database, context.company_id, payload.assignee_user_id)
    if "requester_contact_id" in payload.model_fields_set:
        await _validate_requester(database, context.company_id, payload.requester_contact_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(ticket, field, value)
    if payload.status in {"resolved", "closed"} and ticket.resolved_at is None:
        ticket.resolved_at = utc_now()
    elif payload.status in {"open", "in_progress", "waiting"}:
        ticket.resolved_at = None
    ticket.updated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="support.ticket.updated",
        target_type="support_ticket",
        target_id=ticket.id,
        details={"fields": sorted(payload.model_fields_set)},
    )
    await database.commit()
    await database.refresh(ticket)
    return _ticket_response(ticket)


@router.get("/tickets/{ticket_id}/interactions", response_model=list[SupportInteractionResponse])
async def list_interactions(
    ticket_id: UUID,
    principal: CanViewTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> list[SupportInteractionResponse]:
    context = get_request_context(principal)
    await _ticket(database, context.company_id, ticket_id)
    interactions = list(
        await database.scalars(
            select(SupportInteraction)
            .where(
                SupportInteraction.company_id == context.company_id,
                SupportInteraction.ticket_id == ticket_id,
            )
            .order_by(SupportInteraction.created_at)
        )
    )
    return [
        SupportInteractionResponse.model_validate(interaction, from_attributes=True)
        for interaction in interactions
    ]


@router.post(
    "/tickets/{ticket_id}/interactions",
    response_model=SupportInteractionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_interaction(
    ticket_id: UUID,
    payload: SupportInteractionCreate,
    principal: CanCommentTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportInteractionResponse:
    context = get_request_context(principal)
    ticket = await _ticket(database, context.company_id, ticket_id)
    interaction = SupportInteraction(
        company_id=context.company_id,
        ticket_id=ticket.id,
        author_user_id=context.user_id,
        **payload.model_dump(),
    )
    database.add(interaction)
    ticket.updated_at = utc_now()
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="support.interaction.created",
        target_type="support_ticket",
        target_id=ticket.id,
        details={"internal": interaction.is_internal},
    )
    await database.commit()
    await database.refresh(interaction)
    return SupportInteractionResponse.model_validate(interaction, from_attributes=True)
