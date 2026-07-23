from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utc_now
from app.modules.agents.runtime_models import AgentDispatchReview, AgentRuntimeDispatch
from app.modules.agents.runtime_service import credential_readiness
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event


@dataclass(frozen=True, slots=True)
class DispatchReviewError(RuntimeError):
    code: str
    detail: str


def _record_review_event(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    action: str,
    review: AgentDispatchReview,
) -> None:
    details = {
        "agent_id": str(review.agent_id),
        "interrupted_dispatch_id": str(review.interrupted_dispatch_id),
        "replacement_dispatch_id": str(review.replacement_dispatch_id or ""),
        "decision": review.decision,
        "status": review.status,
    }
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type="agent_dispatch_review",
        target_id=review.id,
        details=details,
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=action,
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={"review_id": str(review.id), **details},
        ),
    )


async def create_dispatch_review(
    database: AsyncSession,
    *,
    company_id: UUID,
    agent_id: UUID,
    dispatch_id: UUID,
    actor_user_id: UUID,
    decision: Literal["close", "retry"],
    reason: str,
    idempotency_key: UUID,
) -> AgentDispatchReview:
    replay = await database.scalar(
        select(AgentDispatchReview).where(
            AgentDispatchReview.company_id == company_id,
            AgentDispatchReview.request_idempotency_key == idempotency_key,
        )
    )
    if replay is not None:
        if replay.interrupted_dispatch_id == dispatch_id and replay.decision == decision:
            return replay
        raise DispatchReviewError(
            "idempotency_conflict", "A chave de idempotência já foi usada em outra decisão."
        )
    dispatch = await database.scalar(
        select(AgentRuntimeDispatch)
        .where(
            AgentRuntimeDispatch.id == dispatch_id,
            AgentRuntimeDispatch.company_id == company_id,
            AgentRuntimeDispatch.agent_id == agent_id,
        )
        .with_for_update()
    )
    if dispatch is None:
        raise DispatchReviewError("dispatch_not_found", "Despacho não encontrado nesta empresa.")
    if dispatch.status != "failed" or dispatch.error_code != "execution_interrupted_manual_review":
        raise DispatchReviewError(
            "dispatch_not_reviewable", "Somente interrupções pendentes de revisão podem ser decididas."
        )
    existing = await database.scalar(
        select(AgentDispatchReview).where(
            AgentDispatchReview.company_id == company_id,
            AgentDispatchReview.interrupted_dispatch_id == dispatch_id,
        )
    )
    if existing is not None:
        raise DispatchReviewError("review_already_exists", "Este despacho já recebeu uma decisão.")
    review = AgentDispatchReview(
        company_id=company_id,
        agent_id=agent_id,
        interrupted_dispatch_id=dispatch_id,
        decision=decision,
        status="closed" if decision == "close" else "pending_approval",
        reason=reason.strip(),
        request_idempotency_key=idempotency_key,
        requested_by_user_id=actor_user_id,
    )
    database.add(review)
    await database.flush()
    _record_review_event(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="agent.dispatch.reviewed",
        review=review,
    )
    return review


async def approve_dispatch_retry(
    database: AsyncSession,
    *,
    company_id: UUID,
    agent_id: UUID,
    review_id: UUID,
    actor_user_id: UUID,
    idempotency_key: UUID,
) -> AgentDispatchReview:
    review = await database.scalar(
        select(AgentDispatchReview)
        .where(
            AgentDispatchReview.id == review_id,
            AgentDispatchReview.company_id == company_id,
            AgentDispatchReview.agent_id == agent_id,
        )
        .with_for_update()
    )
    if review is None:
        raise DispatchReviewError("review_not_found", "Revisão não encontrada nesta empresa.")
    if review.approval_idempotency_key == idempotency_key and review.status == "approved":
        return review
    if review.status != "pending_approval" or review.decision != "retry":
        raise DispatchReviewError("review_not_pending", "Esta revisão não aguarda aprovação.")
    replay = await database.scalar(
        select(AgentDispatchReview.id).where(
            AgentDispatchReview.company_id == company_id,
            AgentDispatchReview.approval_idempotency_key == idempotency_key,
            AgentDispatchReview.id != review.id,
        )
    )
    if replay is not None:
        raise DispatchReviewError(
            "idempotency_conflict", "A chave de idempotência já aprovou outra repetição."
        )
    interrupted = await database.scalar(
        select(AgentRuntimeDispatch).where(
            AgentRuntimeDispatch.id == review.interrupted_dispatch_id,
            AgentRuntimeDispatch.company_id == company_id,
            AgentRuntimeDispatch.agent_id == agent_id,
        )
    )
    if interrupted is None:
        raise DispatchReviewError("dispatch_not_found", "O despacho interrompido não existe mais.")
    readiness = await credential_readiness(
        database,
        company_id=company_id,
        agent_id=agent_id,
        required_tool_keys=interrupted.required_tool_keys,
    )
    replacement = AgentRuntimeDispatch(
        company_id=company_id,
        agent_id=agent_id,
        agent_version_id=interrupted.agent_version_id,
        schedule_id=interrupted.schedule_id,
        trigger_id=interrupted.trigger_id,
        source_event_id=interrupted.source_event_id,
        retry_of_dispatch_id=interrupted.id,
        source_type="retry",
        status="ready" if readiness.ready else "blocked",
        reason_code=readiness.reason_code,
        objective_fingerprint=interrupted.objective_fingerprint,
        required_tool_keys=list(interrupted.required_tool_keys),
        credential_binding_ids=[str(value) for value in readiness.binding_ids],
        tool_arguments=dict(interrupted.tool_arguments),
        execution_mode=interrupted.execution_mode,
        canary_percentage=interrupted.canary_percentage,
        scheduled_for=utc_now(),
    )
    database.add(replacement)
    await database.flush()
    review.status = "approved"
    review.approval_idempotency_key = idempotency_key
    review.approved_by_user_id = actor_user_id
    review.approved_at = utc_now()
    review.replacement_dispatch_id = replacement.id
    _record_review_event(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="agent.dispatch.retry_approved",
        review=review,
    )
    return review
