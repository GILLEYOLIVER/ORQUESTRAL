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
from app.modules.agents.runtime_models import AgentDispatchReview, AgentRuntimeDispatch
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


async def dispatch_review_summary(
    database: AsyncSession,
    *,
    company_id: UUID,
    agent_id: UUID,
    sla_minutes: int,
) -> DispatchReviewSummary:
    now = utc_now()
    overdue_before = now - timedelta(minutes=sla_minutes)
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
        sla_minutes=sla_minutes,
    )


async def maintain_agent_dispatch_review_sla(
    *,
    settings: Settings | None = None,
    sla_minutes: int = 30,
    limit: int = 200,
) -> dict[str, int]:
    active_settings = settings or get_settings()
    resources = create_resources(active_settings)
    now = utc_now()
    overdue_before = now - timedelta(minutes=max(5, sla_minutes))
    result = {"review_breaches": 0, "notifications": 0}
    try:
        async with resources.sessions() as database:
            reviews = list(
                await database.scalars(
                    select(AgentDispatchReview)
                    .where(
                        AgentDispatchReview.status == "pending_approval",
                        AgentDispatchReview.created_at <= overdue_before,
                    )
                    .order_by(AgentDispatchReview.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(max(1, min(limit, 500)))
                )
            )
            for review in reviews:
                already_recorded = await database.scalar(
                    select(OutboxEvent.id).where(
                        OutboxEvent.company_id == review.company_id,
                        OutboxEvent.event_type == "agent.dispatch.review_sla_breached",
                        OutboxEvent.payload["review_id"].as_string() == str(review.id),
                    )
                )
                if already_recorded is not None:
                    continue
                overdue_minutes = max(0, int((now - review.created_at).total_seconds() // 60))
                recipients = await company_approver_user_ids(database, review.company_id)
                if not recipients:
                    recipients = [review.requested_by_user_id]
                for recipient_id in dict.fromkeys(recipients):
                    notification = await create_notification(
                        database,
                        company_id=review.company_id,
                        recipient_user_id=recipient_id,
                        event_type="agent.dispatch.review_sla_breached",
                        title="Revisão de agente fora do prazo",
                        message="Uma execução interrompida aguarda aprovação administrativa.",
                        severity="warning",
                        resource_type="agent_dispatch_review",
                        resource_id=review.id,
                        data={
                            "agent_id": str(review.agent_id),
                            "review_id": str(review.id),
                            "overdue_minutes": overdue_minutes,
                            "sla_minutes": max(5, sla_minutes),
                        },
                    )
                    if notification is not None:
                        result["notifications"] += 1
                enqueue_domain_event(
                    database,
                    DomainEventCreate(
                        event_type="agent.dispatch.review_sla_breached",
                        company_id=review.company_id,
                        actor_user_id=review.requested_by_user_id,
                        classification="internal",
                        payload={
                            "agent_id": str(review.agent_id),
                            "review_id": str(review.id),
                            "overdue_minutes": overdue_minutes,
                            "sla_minutes": max(5, sla_minutes),
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
