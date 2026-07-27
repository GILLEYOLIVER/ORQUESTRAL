from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import (
    apply_tenant_database_context,
    create_database_engine,
    create_session_factory,
)
from app.modules.authorization.service import record_authorization_audit
from app.modules.companies.models import Company
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.notifications.service import create_notification
from app.modules.support.escalation_schemas import (
    SupportEscalationMaintenanceResponse,
    SupportEscalationSummary,
)
from app.modules.support.models import (
    SupportBusinessCalendar,
    SupportEscalationEvent,
    SupportEscalationPolicy,
    SupportTicket,
)

EscalationPhase = Literal["warning", "breach"]
_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def escalation_phase(
    *,
    deadline: datetime,
    now: datetime,
    warning_minutes_before: int,
) -> EscalationPhase | None:
    if now >= deadline:
        return "breach"
    if now >= deadline - timedelta(minutes=warning_minutes_before):
        return "warning"
    return None


def calendar_is_open(
    *,
    weekly_schedule: dict[str, object],
    holidays: list[str],
    timezone_name: str,
    moment: datetime,
) -> bool:
    local = moment.astimezone(ZoneInfo(timezone_name))
    if local.date().isoformat() in set(holidays):
        return False
    windows = weekly_schedule.get(_WEEKDAYS[local.weekday()], [])
    if not isinstance(windows, list):
        return False
    current = local.timetz().replace(tzinfo=None)
    for raw_window in windows:
        if not isinstance(raw_window, dict):
            continue
        try:
            start = time.fromisoformat(str(raw_window["start"]))
            end = time.fromisoformat(str(raw_window["end"]))
        except (KeyError, ValueError):
            continue
        if start <= current < end:
            return True
    return False


def _ticket_deadline(ticket: SupportTicket) -> datetime | None:
    if ticket.status in {"resolved", "closed"}:
        return None
    if ticket.first_responded_at is None and ticket.first_response_due_at is not None:
        return ticket.first_response_due_at
    return ticket.resolution_due_at


async def _event_exists(
    database: AsyncSession,
    *,
    company_id: UUID,
    ticket_id: UUID,
    policy_id: UUID,
    phase: EscalationPhase,
    deadline: datetime,
) -> bool:
    return (
        await database.scalar(
            select(SupportEscalationEvent.id).where(
                SupportEscalationEvent.company_id == company_id,
                SupportEscalationEvent.ticket_id == ticket_id,
                SupportEscalationEvent.policy_id == policy_id,
                SupportEscalationEvent.kind == phase,
                SupportEscalationEvent.deadline_at == deadline,
            )
        )
        is not None
    )


async def maintain_company_sla_escalations(
    database: AsyncSession,
    *,
    company_id: UUID,
    now: datetime | None = None,
) -> SupportEscalationMaintenanceResponse:
    current = now or datetime.now(UTC)
    result = {"evaluated": 0, "warnings": 0, "escalations": 0, "skipped_outside_calendar": 0}
    policies = list(
        await database.scalars(
            select(SupportEscalationPolicy).where(
                SupportEscalationPolicy.company_id == company_id,
                SupportEscalationPolicy.is_active.is_(True),
            )
        )
    )
    for policy in policies:
        calendar = await database.scalar(
            select(SupportBusinessCalendar).where(
                SupportBusinessCalendar.company_id == company_id,
                SupportBusinessCalendar.id == policy.calendar_id,
                SupportBusinessCalendar.is_active.is_(True),
            )
        )
        if calendar is None:
            continue
        tickets = list(
            await database.scalars(
                select(SupportTicket).where(
                    SupportTicket.company_id == company_id,
                    SupportTicket.sla_policy_id == policy.sla_policy_id,
                    SupportTicket.status.in_(("open", "in_progress", "waiting")),
                )
            )
        )
        for ticket in tickets:
            deadline = _ticket_deadline(ticket)
            if deadline is None:
                continue
            result["evaluated"] += 1
            phase = escalation_phase(
                deadline=deadline,
                now=current,
                warning_minutes_before=policy.warning_minutes_before,
            )
            if phase is None:
                continue
            if not calendar_is_open(
                weekly_schedule=calendar.weekly_schedule,
                holidays=calendar.holidays,
                timezone_name=calendar.timezone,
                moment=current,
            ):
                result["skipped_outside_calendar"] += 1
                continue
            if await _event_exists(
                database,
                company_id=company_id,
                ticket_id=ticket.id,
                policy_id=policy.id,
                phase=phase,
                deadline=deadline,
            ):
                continue

            recipient_user_id = policy.escalation_user_id or policy.created_by_user_id
            if phase == "breach":
                ticket.breached_at = ticket.breached_at or current
                if policy.action == "prioritize":
                    ticket.priority = "urgent"
                elif policy.action == "reassign_queue":
                    ticket.queue_id = policy.escalation_queue_id
                elif policy.action == "reassign_user":
                    ticket.assignee_user_id = policy.escalation_user_id

            event = SupportEscalationEvent(
                company_id=company_id,
                ticket_id=ticket.id,
                policy_id=policy.id,
                kind=phase,
                action=policy.action,
                deadline_at=deadline,
                details={
                    "calendar_id": str(calendar.id),
                    "minutes_overdue": max(
                        0,
                        int((current - deadline).total_seconds() // 60),
                    ),
                },
            )
            try:
                async with database.begin_nested():
                    database.add(event)
                    await database.flush()
            except IntegrityError:
                continue
            event_type = (
                "support.sla.warning" if phase == "warning" else "support.sla.escalated"
            )
            await create_notification(
                database,
                company_id=company_id,
                recipient_user_id=recipient_user_id,
                event_type=event_type,
                title=(
                    "SLA próximo do vencimento"
                    if phase == "warning"
                    else "SLA vencido e escalonado"
                ),
                message="Um chamado com SLA controlado requer atenção.",
                severity="warning" if phase == "warning" else "error",
                resource_type="support_ticket",
                resource_id=ticket.id,
                data={"event_id": str(event.id), "phase": phase},
            )
            record_authorization_audit(
                database,
                company_id=company_id,
                actor_user_id=policy.created_by_user_id,
                action=event_type,
                target_type="support_ticket",
                target_id=ticket.id,
                details={
                    "policy_id": str(policy.id),
                    "event_id": str(event.id),
                    "action": policy.action,
                },
            )
            enqueue_domain_event(
                database,
                DomainEventCreate(
                    event_type=event_type,
                    company_id=company_id,
                    actor_user_id=policy.created_by_user_id,
                    classification="internal",
                    payload={
                        "ticket_id": str(ticket.id),
                        "policy_id": str(policy.id),
                        "event_id": str(event.id),
                        "action": policy.action,
                    },
                ),
            )
            result["warnings" if phase == "warning" else "escalations"] += 1
    await database.flush()
    return SupportEscalationMaintenanceResponse(**result)


async def escalation_summary(
    database: AsyncSession,
    *,
    company_id: UUID,
    now: datetime | None = None,
) -> SupportEscalationSummary:
    current = now or datetime.now(UTC)
    warning_limit = current + timedelta(minutes=60)
    active_policies = int(
        await database.scalar(
            select(func.count(SupportEscalationPolicy.id)).where(
                SupportEscalationPolicy.company_id == company_id,
                SupportEscalationPolicy.is_active.is_(True),
            )
        )
        or 0
    )
    due_soon = int(
        await database.scalar(
            select(func.count(SupportTicket.id)).where(
                SupportTicket.company_id == company_id,
                SupportTicket.status.in_(("open", "in_progress", "waiting")),
                SupportTicket.resolution_due_at.is_not(None),
                SupportTicket.resolution_due_at <= warning_limit,
                SupportTicket.resolution_due_at > current,
            )
        )
        or 0
    )
    breached = int(
        await database.scalar(
            select(func.count(SupportTicket.id)).where(
                SupportTicket.company_id == company_id,
                SupportTicket.breached_at.is_not(None),
                SupportTicket.status.in_(("open", "in_progress", "waiting")),
            )
        )
        or 0
    )
    warnings_sent = int(
        await database.scalar(
            select(func.count(SupportEscalationEvent.id)).where(
                SupportEscalationEvent.company_id == company_id,
                SupportEscalationEvent.kind == "warning",
            )
        )
        or 0
    )
    escalations_applied = int(
        await database.scalar(
            select(func.count(SupportEscalationEvent.id)).where(
                SupportEscalationEvent.company_id == company_id,
                SupportEscalationEvent.kind == "breach",
            )
        )
        or 0
    )
    default_calendar = await database.scalar(
        select(SupportBusinessCalendar).where(
            SupportBusinessCalendar.company_id == company_id,
            SupportBusinessCalendar.is_default.is_(True),
            SupportBusinessCalendar.is_active.is_(True),
        )
    )
    return SupportEscalationSummary(
        active_policies=active_policies,
        due_soon=due_soon,
        breached=breached,
        warnings_sent=warnings_sent,
        escalations_applied=escalations_applied,
        calendar_open=bool(
            default_calendar
            and calendar_is_open(
                weekly_schedule=default_calendar.weekly_schedule,
                holidays=default_calendar.holidays,
                timezone_name=default_calendar.timezone,
                moment=current,
            )
        ),
    )


async def maintain_support_sla_escalations() -> dict[str, int]:
    settings = get_settings()
    engine = create_database_engine(str(settings.database_url))
    sessions = create_session_factory(engine)
    totals = {
        "companies": 0,
        "evaluated": 0,
        "warnings": 0,
        "escalations": 0,
        "skipped_outside_calendar": 0,
    }
    try:
        async with sessions() as root:
            company_ids = list(
                await root.scalars(
                    select(Company.id).where(
                        Company.status.in_(("active", "trial")),
                        Company.deleted_at.is_(None),
                    )
                )
            )
        for company_id in company_ids:
            async with sessions() as database:
                await apply_tenant_database_context(
                    database,
                    company_id=company_id,
                    access_mode="standard",
                )
                result = await maintain_company_sla_escalations(
                    database,
                    company_id=company_id,
                )
                await database.commit()
                totals["companies"] += 1
                for field in (
                    "evaluated",
                    "warnings",
                    "escalations",
                    "skipped_outside_calendar",
                ):
                    totals[field] += getattr(result, field)
        return totals
    finally:
        await engine.dispose()


def maintain_support_sla_escalations_sync() -> dict[str, int]:
    return asyncio.run(maintain_support_sla_escalations())
