from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.resources import create_resources
from app.core.security import utc_now
from app.modules.agents.review_assignment_service import (
    assign_review_for_sla,
    current_review_assignment,
)
from app.modules.agents.runtime_models import (
    AgentDispatchReview,
    AgentDispatchReviewSLAPolicy,
    AgentRuntimeDispatch,
)
from app.modules.events.models import OutboxEvent
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.notifications.service import company_approver_user_ids, create_notification


@dataclass(frozen=True, slots=True)
class DispatchReviewSummary:
    pending: int
    overdue: int
    closed: int
    approved: int
    repeat_interruptions: int
    average_decision_minutes: float | None
    oldest_pending_minutes: int | None
    retry_rate_percent: float
    sla_minutes: int
    escalation_minutes: int
    policy_version: int | None


@dataclass(frozen=True, slots=True)
class ReviewSLASettings:
    policy_id: UUID | None
    sla_minutes: int
    escalation_minutes: int
    policy_version: int | None
    acknowledgement_minutes: int
    on_call_user_ids: tuple[UUID, ...]
    on_call_timezone: str
    on_call_start_hour: int
    on_call_end_hour: int
    on_call_weekdays: tuple[int, ...]
    on_call_shifts: tuple[dict[str, object], ...]
    holiday_calendar: tuple[dict[str, object], ...]
    minimum_coverage: int


async def effective_review_sla(
    database: AsyncSession, *, company_id: UUID, agent_id: UUID
) -> ReviewSLASettings:
    policy = await database.scalar(
        select(AgentDispatchReviewSLAPolicy).where(
            AgentDispatchReviewSLAPolicy.company_id == company_id,
            AgentDispatchReviewSLAPolicy.agent_id == agent_id,
            AgentDispatchReviewSLAPolicy.status == "published",
        )
    )
    return (
        ReviewSLASettings(
            policy.id,
            policy.sla_minutes,
            policy.escalation_minutes,
            policy.version,
            policy.acknowledgement_minutes,
            tuple(UUID(value) for value in policy.on_call_user_ids),
            policy.on_call_timezone,
            policy.on_call_start_hour,
            policy.on_call_end_hour,
            tuple(policy.on_call_weekdays),
            tuple(policy.on_call_shifts),
            tuple(policy.holiday_calendar),
            policy.minimum_coverage,
        )
        if policy is not None
        else ReviewSLASettings(
            None, 30, 120, None, 15, (), "UTC", 0, 24, tuple(range(7)), (), (), 1
        )
    )


async def dispatch_review_summary(
    database: AsyncSession,
    *,
    company_id: UUID,
    agent_id: UUID,
    sla_minutes: int | None,
) -> DispatchReviewSummary:
    configured = await effective_review_sla(database, company_id=company_id, agent_id=agent_id)
    effective_minutes = sla_minutes or configured.sla_minutes
    now = utc_now()
    overdue_before = now - timedelta(minutes=effective_minutes)
    row = (
        await database.execute(
            select(
                func.count(AgentDispatchReview.id)
                .filter(AgentDispatchReview.status == "pending_approval")
                .label("pending"),
                func.count(AgentDispatchReview.id)
                .filter(
                    AgentDispatchReview.status == "pending_approval",
                    AgentDispatchReview.created_at <= overdue_before,
                )
                .label("overdue"),
                func.count(AgentDispatchReview.id)
                .filter(AgentDispatchReview.status == "closed")
                .label("closed"),
                func.count(AgentDispatchReview.id)
                .filter(AgentDispatchReview.status == "approved")
                .label("approved"),
                func.count(AgentDispatchReview.id)
                .filter(AgentDispatchReview.decision == "retry")
                .label("retry_decisions"),
                func.count(AgentDispatchReview.id).label("total"),
                func.avg(
                    func.extract(
                        "epoch", AgentDispatchReview.updated_at - AgentDispatchReview.created_at
                    )
                    / 60.0
                )
                .filter(AgentDispatchReview.status.in_(("closed", "approved")))
                .label("average_decision_minutes"),
                func.min(AgentDispatchReview.created_at)
                .filter(AgentDispatchReview.status == "pending_approval")
                .label("oldest_pending_at"),
            ).where(
                AgentDispatchReview.company_id == company_id,
                AgentDispatchReview.agent_id == agent_id,
            )
        )
    ).one()
    repeat_interruptions = int(
        await database.scalar(
            select(func.count(AgentDispatchReview.id))
            .join(
                AgentRuntimeDispatch,
                AgentRuntimeDispatch.id == AgentDispatchReview.interrupted_dispatch_id,
            )
            .where(
                AgentDispatchReview.company_id == company_id,
                AgentDispatchReview.agent_id == agent_id,
                AgentRuntimeDispatch.company_id == company_id,
                AgentRuntimeDispatch.source_type == "retry",
            )
        )
        or 0
    )
    total = int(row.total or 0)
    retry_decisions = int(row.retry_decisions or 0)
    oldest_pending_minutes = (
        max(0, int((now - row.oldest_pending_at).total_seconds() // 60))
        if row.oldest_pending_at is not None
        else None
    )
    return DispatchReviewSummary(
        pending=int(row.pending or 0),
        overdue=int(row.overdue or 0),
        closed=int(row.closed or 0),
        approved=int(row.approved or 0),
        repeat_interruptions=repeat_interruptions,
        average_decision_minutes=(
            round(float(row.average_decision_minutes), 2)
            if row.average_decision_minutes is not None
            else None
        ),
        oldest_pending_minutes=oldest_pending_minutes,
        retry_rate_percent=round((retry_decisions / total) * 100, 2) if total else 0.0,
        sla_minutes=effective_minutes,
        escalation_minutes=configured.escalation_minutes,
        policy_version=configured.policy_version,
    )


async def maintain_agent_dispatch_review_sla(
    *,
    settings: Settings | None = None,
    sla_minutes: int | None = None,
    limit: int = 200,
) -> dict[str, int]:
    active_settings = settings or get_settings()
    resources = create_resources(active_settings)
    now = utc_now()
    result = {"review_breaches": 0, "notifications": 0}
    try:
        async with resources.sessions() as database:
            reviews = list(
                await database.scalars(
                    select(AgentDispatchReview)
                    .where(
                        AgentDispatchReview.status == "pending_approval",
                    )
                    .order_by(AgentDispatchReview.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(max(1, min(limit, 500)))
                )
            )
            for review in reviews:
                policy = await effective_review_sla(
                    database, company_id=review.company_id, agent_id=review.agent_id
                )
                initial_sla = max(5, sla_minutes) if sla_minutes is not None else policy.sla_minutes
                escalation_minutes = (
                    max(initial_sla + 1, policy.escalation_minutes)
                    if sla_minutes is not None
                    else policy.escalation_minutes
                )
                overdue_minutes = max(0, int((now - review.created_at).total_seconds() // 60))
                current_assignment = await current_review_assignment(
                    database, company_id=review.company_id, review_id=review.id
                )
                acknowledgement_overdue = bool(
                    current_assignment is not None
                    and current_assignment.acknowledged_at is None
                    and (now - current_assignment.assigned_at).total_seconds()
                    >= policy.acknowledgement_minutes * 60
                )
                if acknowledgement_overdue:
                    escalated = True
                    event_type = "agent.dispatch.review_acknowledgement_overdue"
                else:
                    if overdue_minutes < initial_sla:
                        continue
                    escalated = overdue_minutes >= escalation_minutes
                    event_type = (
                        "agent.dispatch.review_sla_escalated"
                        if escalated
                        else "agent.dispatch.review_sla_breached"
                    )
                already_recorded = await database.scalar(
                    select(OutboxEvent.id).where(
                        OutboxEvent.company_id == review.company_id,
                        OutboxEvent.event_type == event_type,
                        OutboxEvent.payload["review_id"].as_string() == str(review.id),
                    )
                )
                if already_recorded is not None:
                    continue
                assignment = await assign_review_for_sla(
                    database,
                    review=review,
                    policy_id=policy.policy_id,
                    on_call_user_ids=policy.on_call_user_ids,
                    on_call_timezone=policy.on_call_timezone,
                    on_call_start_hour=policy.on_call_start_hour,
                    on_call_end_hour=policy.on_call_end_hour,
                    on_call_weekdays=policy.on_call_weekdays,
                    on_call_shifts=policy.on_call_shifts,
                    holiday_calendar=policy.holiday_calendar,
                    escalated=escalated,
                )
                recipients = (
                    [assignment.assigned_to_user_id]
                    if assignment is not None
                    else await company_approver_user_ids(database, review.company_id)
                )
                if not recipients:
                    recipients = [review.requested_by_user_id]
                for recipient_id in dict.fromkeys(recipients):
                    notification = await create_notification(
                        database,
                        company_id=review.company_id,
                        recipient_user_id=recipient_id,
                        event_type=event_type,
                        title=(
                            "Plantão de agente sem confirmação"
                            if acknowledgement_overdue
                            else (
                                "Revisão de agente exige escalonamento"
                                if escalated
                                else "Revisão de agente fora do prazo"
                            )
                        ),
                        message="Uma execução interrompida aguarda aprovação administrativa.",
                        severity="critical" if escalated else "warning",
                        resource_type="agent_dispatch_review",
                        resource_id=review.id,
                        data={
                            "agent_id": str(review.agent_id),
                            "review_id": str(review.id),
                            "overdue_minutes": overdue_minutes,
                            "sla_minutes": initial_sla,
                            "escalation_minutes": escalation_minutes,
                            "acknowledgement_minutes": policy.acknowledgement_minutes,
                            "assignment_id": str(assignment.id) if assignment else None,
                        },
                    )
                    if notification is not None:
                        result["notifications"] += 1
                enqueue_domain_event(
                    database,
                    DomainEventCreate(
                        event_type=event_type,
                        company_id=review.company_id,
                        actor_user_id=review.requested_by_user_id,
                        classification="internal",
                        payload={
                            "agent_id": str(review.agent_id),
                            "review_id": str(review.id),
                            "overdue_minutes": overdue_minutes,
                            "sla_minutes": initial_sla,
                            "escalation_minutes": escalation_minutes,
                            "assignment_id": str(assignment.id) if assignment else None,
                        },
                    ),
                )
                result["review_breaches"] += 1
            await database.commit()
            return result
    finally:
        await resources.close()


def maintain_agent_dispatch_review_sla_sync() -> dict[str, int]:
    return asyncio.run(maintain_agent_dispatch_review_sla())
