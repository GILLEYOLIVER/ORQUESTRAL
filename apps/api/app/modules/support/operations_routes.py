from __future__ import annotations

from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.modularity.dependencies import require_active_module
from app.modules.support.models import (
    SupportInteraction,
    SupportQueue,
    SupportSLAPolicy,
    SupportTicket,
    SupportTicketEvent,
)
from app.modules.support.schemas import (
    SupportDashboardResponse,
    SupportInteractionCreate,
    SupportInteractionResponse,
    SupportQueueCreate,
    SupportQueueResponse,
    SupportSatisfactionCreate,
    SupportSLAPolicyCreate,
    SupportSLAPolicyResponse,
    SupportTicketEventResponse,
    SupportTicketOperationsUpdate,
    SupportTicketResponse,
)
from app.modules.users.models import CompanyUser

router = APIRouter(prefix="/support", tags=["support-operations"])

ActiveSupport = Annotated[Principal, Depends(require_active_module("support"))]
CanViewTickets = Annotated[Principal, Depends(require_permission("support.tickets.view"))]
CanCreateTickets = Annotated[Principal, Depends(require_permission("support.tickets.create"))]
CanUpdateTickets = Annotated[Principal, Depends(require_permission("support.tickets.update"))]
CanCommentTickets = Annotated[Principal, Depends(require_permission("support.tickets.comment"))]

DEFAULT_TARGETS = {
    "low": {"first_response": 480, "resolution": 2880},
    "normal": {"first_response": 240, "resolution": 1440},
    "high": {"first_response": 60, "resolution": 480},
    "urgent": {"first_response": 15, "resolution": 120},
}


async def _ticket(database: DatabaseSession, company_id: UUID, ticket_id: UUID) -> SupportTicket:
    ticket = await database.scalar(
        select(SupportTicket).where(
            SupportTicket.id == ticket_id,
            SupportTicket.company_id == company_id,
        )
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail="Chamado não encontrado.")
    return ticket


async def _ensure_defaults(
    database: DatabaseSession, company_id: UUID
) -> tuple[SupportQueue, SupportSLAPolicy]:
    queue = await database.scalar(
        select(SupportQueue)
        .where(SupportQueue.company_id == company_id, SupportQueue.is_default.is_(True))
        .order_by(SupportQueue.created_at)
    )
    policy = await database.scalar(
        select(SupportSLAPolicy)
        .where(
            SupportSLAPolicy.company_id == company_id,
            SupportSLAPolicy.is_default.is_(True),
        )
        .order_by(SupportSLAPolicy.created_at)
    )
    created = False
    if queue is None:
        queue = SupportQueue(
            company_id=company_id,
            name="Atendimento geral",
            key="geral",
            description="Fila padrão para novos pedidos de atendimento.",
            is_default=True,
        )
        database.add(queue)
        created = True
    if policy is None:
        policy = SupportSLAPolicy(
            company_id=company_id,
            name="SLA padrão",
            description="Metas iniciais por prioridade, válidas durante todo o período.",
            targets=DEFAULT_TARGETS,
            is_default=True,
        )
        database.add(policy)
        created = True
    if created:
        try:
            await database.commit()
        except IntegrityError:
            await database.rollback()
            return await _ensure_defaults(database, company_id)
        await database.refresh(queue)
        await database.refresh(policy)
    return queue, policy


def _apply_sla(ticket: SupportTicket, policy: SupportSLAPolicy) -> None:
    target = policy.targets.get(ticket.priority, DEFAULT_TARGETS[ticket.priority])
    ticket.sla_policy_id = policy.id
    ticket.first_response_due_at = ticket.created_at + timedelta(
        minutes=int(target["first_response"])
    )
    ticket.resolution_due_at = ticket.created_at + timedelta(minutes=int(target["resolution"]))


def _event(
    ticket: SupportTicket,
    actor_user_id: UUID | None,
    event_type: str,
    description: str,
    details: dict[str, object] | None = None,
) -> SupportTicketEvent:
    return SupportTicketEvent(
        company_id=ticket.company_id,
        ticket_id=ticket.id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        description=description,
        details=details or {},
    )


def _ticket_response(ticket: SupportTicket) -> SupportTicketResponse:
    return SupportTicketResponse.model_validate(ticket, from_attributes=True)


def _queue_response(queue: SupportQueue, tickets: list[SupportTicket]) -> SupportQueueResponse:
    queue_tickets = [
        ticket
        for ticket in tickets
        if ticket.queue_id == queue.id and ticket.status not in {"resolved", "closed"}
    ]
    return SupportQueueResponse(
        id=queue.id,
        name=queue.name,
        key=queue.key,
        description=queue.description,
        color=queue.color,
        is_default=queue.is_default,
        is_active=queue.is_active,
        open_tickets=len(queue_tickets),
        unassigned_tickets=sum(ticket.assignee_user_id is None for ticket in queue_tickets),
        breached_tickets=sum(ticket.breached_at is not None for ticket in queue_tickets),
    )


@router.get("/dashboard", response_model=SupportDashboardResponse)
async def support_dashboard(
    principal: CanViewTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportDashboardResponse:
    context = get_request_context(principal)
    default_queue, default_policy = await _ensure_defaults(database, context.company_id)
    tickets = list(
        await database.scalars(
            select(SupportTicket).where(SupportTicket.company_id == context.company_id)
        )
    )
    now = utc_now()
    changed = False
    for ticket in tickets:
        if ticket.queue_id is None:
            ticket.queue_id = default_queue.id
            changed = True
        if ticket.sla_policy_id is None:
            _apply_sla(ticket, default_policy)
            changed = True
        deadline = (
            ticket.first_response_due_at
            if ticket.first_responded_at is None
            else ticket.resolution_due_at
        )
        if (
            ticket.status not in {"resolved", "closed"}
            and deadline is not None
            and deadline < now
            and ticket.breached_at is None
        ):
            ticket.breached_at = now
            database.add(
                _event(
                    ticket,
                    None,
                    "sla_breached",
                    "O prazo de SLA foi ultrapassado.",
                    {"deadline": deadline.isoformat()},
                )
            )
            changed = True
    if changed:
        await database.commit()

    active = [ticket for ticket in tickets if ticket.status not in {"resolved", "closed"}]
    first_response_values = [
        (ticket.first_responded_at - ticket.created_at).total_seconds() / 60
        for ticket in tickets
        if ticket.first_responded_at is not None
    ]
    satisfaction_values = [
        ticket.satisfaction_score for ticket in tickets if ticket.satisfaction_score is not None
    ]
    due_limit = now + timedelta(hours=2)
    return SupportDashboardResponse(
        open_tickets=len(active),
        unassigned_tickets=sum(ticket.assignee_user_id is None for ticket in active),
        waiting_tickets=sum(ticket.status == "waiting" for ticket in active),
        breached_tickets=sum(ticket.breached_at is not None for ticket in active),
        due_soon_tickets=sum(
            ticket.resolution_due_at is not None and now <= ticket.resolution_due_at <= due_limit
            for ticket in active
        ),
        resolved_today=sum(
            ticket.resolved_at is not None and ticket.resolved_at.date() == now.date()
            for ticket in tickets
        ),
        average_first_response_minutes=round(
            sum(first_response_values) / len(first_response_values), 1
        )
        if first_response_values
        else 0,
        satisfaction_average=round(sum(satisfaction_values) / len(satisfaction_values), 2)
        if satisfaction_values
        else 0,
        satisfaction_responses=len(satisfaction_values),
    )


@router.get("/queues", response_model=list[SupportQueueResponse])
async def list_queues(
    principal: CanViewTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> list[SupportQueueResponse]:
    context = get_request_context(principal)
    await _ensure_defaults(database, context.company_id)
    queues = list(
        await database.scalars(
            select(SupportQueue)
            .where(SupportQueue.company_id == context.company_id, SupportQueue.is_active.is_(True))
            .order_by(SupportQueue.is_default.desc(), SupportQueue.name)
        )
    )
    tickets = list(
        await database.scalars(
            select(SupportTicket).where(SupportTicket.company_id == context.company_id)
        )
    )
    return [_queue_response(queue, tickets) for queue in queues]


@router.post("/queues", response_model=SupportQueueResponse, status_code=status.HTTP_201_CREATED)
async def create_queue(
    payload: SupportQueueCreate,
    principal: CanCreateTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportQueueResponse:
    context = get_request_context(principal)
    queue = SupportQueue(company_id=context.company_id, **payload.model_dump())
    database.add(queue)
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Já existe uma fila com esta chave.") from exc
    await database.refresh(queue)
    return _queue_response(queue, [])


@router.get("/sla-policies", response_model=list[SupportSLAPolicyResponse])
async def list_sla_policies(
    principal: CanViewTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> list[SupportSLAPolicyResponse]:
    context = get_request_context(principal)
    await _ensure_defaults(database, context.company_id)
    policies = list(
        await database.scalars(
            select(SupportSLAPolicy)
            .where(
                SupportSLAPolicy.company_id == context.company_id,
                SupportSLAPolicy.is_active.is_(True),
            )
            .order_by(SupportSLAPolicy.is_default.desc(), SupportSLAPolicy.name)
        )
    )
    return [
        SupportSLAPolicyResponse.model_validate(policy, from_attributes=True) for policy in policies
    ]


@router.post(
    "/sla-policies",
    response_model=SupportSLAPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_sla_policy(
    payload: SupportSLAPolicyCreate,
    principal: CanCreateTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportSLAPolicyResponse:
    context = get_request_context(principal)
    policy = SupportSLAPolicy(company_id=context.company_id, **payload.model_dump())
    database.add(policy)
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(
            status_code=409, detail="Já existe uma política com este nome."
        ) from exc
    await database.refresh(policy)
    return SupportSLAPolicyResponse.model_validate(policy, from_attributes=True)


@router.patch("/tickets/{ticket_id}/operations", response_model=SupportTicketResponse)
async def update_ticket_operations(
    ticket_id: UUID,
    payload: SupportTicketOperationsUpdate,
    principal: CanUpdateTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportTicketResponse:
    context = get_request_context(principal)
    ticket = await _ticket(database, context.company_id, ticket_id)
    changes = payload.model_dump(exclude_unset=True)
    policy: SupportSLAPolicy | None = None
    if "queue_id" in changes and changes["queue_id"] is not None:
        queue = await database.scalar(
            select(SupportQueue).where(
                SupportQueue.id == changes["queue_id"],
                SupportQueue.company_id == context.company_id,
                SupportQueue.is_active.is_(True),
            )
        )
        if queue is None:
            raise HTTPException(status_code=422, detail="Fila inválida para esta empresa.")
    if "sla_policy_id" in changes and changes["sla_policy_id"] is not None:
        policy = await database.scalar(
            select(SupportSLAPolicy).where(
                SupportSLAPolicy.id == changes["sla_policy_id"],
                SupportSLAPolicy.company_id == context.company_id,
                SupportSLAPolicy.is_active.is_(True),
            )
        )
        if policy is None:
            raise HTTPException(status_code=422, detail="Política de SLA inválida.")
    if "assignee_user_id" in changes and changes["assignee_user_id"] is not None:
        membership = await database.scalar(
            select(CompanyUser.id).where(
                CompanyUser.company_id == context.company_id,
                CompanyUser.user_id == changes["assignee_user_id"],
                CompanyUser.status == "active",
            )
        )
        if membership is None:
            raise HTTPException(status_code=422, detail="Responsável inválido para esta empresa.")

    event_map = {
        "queue_id": ("queue_changed", "Fila de atendimento alterada."),
        "assignee_user_id": ("assigned", "Responsável pelo chamado alterado."),
        "priority": ("priority_changed", "Prioridade do chamado alterada."),
        "status": ("status_changed", "Status do chamado alterado."),
    }
    for field, value in changes.items():
        previous = getattr(ticket, field)
        if previous == value:
            continue
        setattr(ticket, field, value)
        if field in event_map:
            event_type, description = event_map[field]
            database.add(
                _event(
                    ticket,
                    context.user_id,
                    event_type,
                    description,
                    {
                        "from": str(previous) if previous is not None else None,
                        "to": str(value) if value is not None else None,
                    },
                )
            )
    if policy is not None:
        _apply_sla(ticket, policy)
    elif "priority" in changes and ticket.sla_policy_id is not None:
        current_policy = await database.get(SupportSLAPolicy, ticket.sla_policy_id)
        if current_policy is not None:
            _apply_sla(ticket, current_policy)
    if ticket.status in {"resolved", "closed"}:
        ticket.resolved_at = ticket.resolved_at or utc_now()
    elif "status" in changes:
        ticket.resolved_at = None
    await database.commit()
    await database.refresh(ticket)
    return _ticket_response(ticket)


@router.post(
    "/tickets/{ticket_id}/response",
    response_model=SupportInteractionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def respond_to_ticket(
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
        message=payload.message,
        is_internal=payload.is_internal,
    )
    database.add(interaction)
    if not payload.is_internal and ticket.first_responded_at is None:
        ticket.first_responded_at = utc_now()
        database.add(
            _event(
                ticket,
                context.user_id,
                "first_response",
                "Primeira resposta enviada ao cliente.",
                {
                    "minutes": round(
                        (ticket.first_responded_at - ticket.created_at).total_seconds() / 60,
                        1,
                    )
                },
            )
        )
    await database.commit()
    await database.refresh(interaction)
    return SupportInteractionResponse.model_validate(interaction, from_attributes=True)


@router.post("/tickets/{ticket_id}/satisfaction", response_model=SupportTicketResponse)
async def record_satisfaction(
    ticket_id: UUID,
    payload: SupportSatisfactionCreate,
    principal: CanUpdateTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportTicketResponse:
    context = get_request_context(principal)
    ticket = await _ticket(database, context.company_id, ticket_id)
    if ticket.status not in {"resolved", "closed"}:
        raise HTTPException(
            status_code=409,
            detail="A avaliação pode ser registrada depois da resolução do chamado.",
        )
    ticket.satisfaction_score = payload.score
    ticket.satisfaction_comment = payload.comment
    database.add(
        _event(
            ticket,
            context.user_id,
            "satisfaction_received",
            "Avaliação do atendimento registrada.",
            {"score": payload.score},
        )
    )
    await database.commit()
    await database.refresh(ticket)
    return _ticket_response(ticket)


@router.get("/tickets/{ticket_id}/events", response_model=list[SupportTicketEventResponse])
async def list_ticket_events(
    ticket_id: UUID,
    principal: CanViewTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> list[SupportTicketEventResponse]:
    context = get_request_context(principal)
    await _ticket(database, context.company_id, ticket_id)
    events = list(
        await database.scalars(
            select(SupportTicketEvent)
            .where(
                SupportTicketEvent.company_id == context.company_id,
                SupportTicketEvent.ticket_id == ticket_id,
            )
            .order_by(SupportTicketEvent.created_at.desc())
        )
    )
    return [
        SupportTicketEventResponse.model_validate(event, from_attributes=True) for event in events
    ]
