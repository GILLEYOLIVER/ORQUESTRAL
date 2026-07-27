from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.support.escalation_schemas import (
    SupportBusinessCalendarCreate,
    SupportBusinessCalendarResponse,
    SupportEscalationEventResponse,
    SupportEscalationMaintenanceResponse,
    SupportEscalationPolicyCreate,
    SupportEscalationPolicyResponse,
    SupportEscalationSummary,
)
from app.modules.support.escalation_service import (
    escalation_summary,
    maintain_company_sla_escalations,
)
from app.modules.support.models import (
    SupportBusinessCalendar,
    SupportEscalationEvent,
    SupportEscalationPolicy,
    SupportQueue,
    SupportSLAPolicy,
)
from app.modules.users.models import CompanyUser

router = APIRouter(prefix="/support/escalations", tags=["support-escalations"])

CanViewTickets = Annotated[Principal, Depends(require_permission("support.tickets.view"))]
CanUpdateTickets = Annotated[Principal, Depends(require_permission("support.tickets.update"))]


@router.get("/calendars", response_model=list[SupportBusinessCalendarResponse])
async def list_business_calendars(
    principal: CanViewTickets,
    database: DatabaseSession,
) -> list[SupportBusinessCalendar]:
    context = get_request_context(principal)
    return list(
        await database.scalars(
            select(SupportBusinessCalendar)
            .where(SupportBusinessCalendar.company_id == context.company_id)
            .order_by(
                SupportBusinessCalendar.is_default.desc(),
                SupportBusinessCalendar.name,
            )
        )
    )


@router.post(
    "/calendars",
    response_model=SupportBusinessCalendarResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_business_calendar(
    payload: SupportBusinessCalendarCreate,
    principal: CanUpdateTickets,
    database: DatabaseSession,
) -> SupportBusinessCalendar:
    context = get_request_context(principal)
    if payload.is_default:
        await database.execute(
            update(SupportBusinessCalendar)
            .where(SupportBusinessCalendar.company_id == context.company_id)
            .values(is_default=False)
        )
    calendar = SupportBusinessCalendar(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        updated_by_user_id=context.user_id,
        name=payload.name,
        timezone=payload.timezone,
        weekly_schedule={
            day: [window.model_dump(mode="json") for window in windows]
            for day, windows in payload.weekly_schedule.items()
        },
        holidays=[holiday.isoformat() for holiday in payload.holidays],
        is_default=payload.is_default,
    )
    database.add(calendar)
    try:
        await database.flush()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Já existe um calendário com esse nome.") from exc
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="support.calendar.created",
        target_type="support_business_calendar",
        target_id=calendar.id,
        details={"timezone": calendar.timezone, "is_default": calendar.is_default},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="support.sla.configuration_updated",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="internal",
            payload={"resource": "calendar", "resource_id": str(calendar.id)},
        ),
    )
    await database.commit()
    await database.refresh(calendar)
    return calendar


@router.get("/policies", response_model=list[SupportEscalationPolicyResponse])
async def list_escalation_policies(
    principal: CanViewTickets,
    database: DatabaseSession,
) -> list[SupportEscalationPolicy]:
    context = get_request_context(principal)
    return list(
        await database.scalars(
            select(SupportEscalationPolicy)
            .where(SupportEscalationPolicy.company_id == context.company_id)
            .order_by(SupportEscalationPolicy.created_at.desc())
        )
    )


@router.post(
    "/policies",
    response_model=SupportEscalationPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_escalation_policy(
    payload: SupportEscalationPolicyCreate,
    principal: CanUpdateTickets,
    database: DatabaseSession,
) -> SupportEscalationPolicy:
    context = get_request_context(principal)
    sla_exists = await database.scalar(
        select(SupportSLAPolicy.id).where(
            SupportSLAPolicy.company_id == context.company_id,
            SupportSLAPolicy.id == payload.sla_policy_id,
            SupportSLAPolicy.is_active.is_(True),
        )
    )
    calendar_exists = await database.scalar(
        select(SupportBusinessCalendar.id).where(
            SupportBusinessCalendar.company_id == context.company_id,
            SupportBusinessCalendar.id == payload.calendar_id,
            SupportBusinessCalendar.is_active.is_(True),
        )
    )
    if sla_exists is None or calendar_exists is None:
        raise HTTPException(status_code=404, detail="SLA ou calendário não encontrado.")
    if payload.escalation_queue_id is not None:
        queue_exists = await database.scalar(
            select(SupportQueue.id).where(
                SupportQueue.company_id == context.company_id,
                SupportQueue.id == payload.escalation_queue_id,
                SupportQueue.is_active.is_(True),
            )
        )
        if queue_exists is None:
            raise HTTPException(status_code=404, detail="Fila de escalonamento não encontrada.")
    if payload.escalation_user_id is not None:
        user_exists = await database.scalar(
            select(CompanyUser.user_id).where(
                CompanyUser.company_id == context.company_id,
                CompanyUser.user_id == payload.escalation_user_id,
                CompanyUser.status == "active",
            )
        )
        if user_exists is None:
            raise HTTPException(status_code=404, detail="Usuário de escalonamento não encontrado.")
    policy = SupportEscalationPolicy(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    database.add(policy)
    try:
        await database.flush()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Já existe uma política com esse nome.") from exc
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="support.escalation_policy.created",
        target_type="support_escalation_policy",
        target_id=policy.id,
        details={"action": policy.action, "warning_minutes": policy.warning_minutes_before},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="support.sla.configuration_updated",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="internal",
            payload={"resource": "policy", "resource_id": str(policy.id)},
        ),
    )
    await database.commit()
    await database.refresh(policy)
    return policy


@router.get("/summary", response_model=SupportEscalationSummary)
async def get_escalation_summary(
    principal: CanViewTickets,
    database: DatabaseSession,
) -> SupportEscalationSummary:
    context = get_request_context(principal)
    return await escalation_summary(database, company_id=context.company_id)


@router.get("/events", response_model=list[SupportEscalationEventResponse])
async def list_escalation_events(
    principal: CanViewTickets,
    database: DatabaseSession,
) -> list[SupportEscalationEvent]:
    context = get_request_context(principal)
    return list(
        await database.scalars(
            select(SupportEscalationEvent)
            .where(SupportEscalationEvent.company_id == context.company_id)
            .order_by(SupportEscalationEvent.occurred_at.desc())
            .limit(100)
        )
    )


@router.post("/maintain", response_model=SupportEscalationMaintenanceResponse)
async def maintain_escalations_now(
    principal: CanUpdateTickets,
    database: DatabaseSession,
) -> SupportEscalationMaintenanceResponse:
    context = get_request_context(principal)
    result = await maintain_company_sla_escalations(
        database,
        company_id=context.company_id,
    )
    await database.commit()
    return result
