from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utc_now
from app.modules.agents.runtime_models import (
    AgentDispatchReview,
    AgentDispatchReviewAssignment,
    AgentDispatchReviewOnCallException,
    AgentDispatchReviewOnCallHandoff,
)
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.notifications.service import company_approver_user_ids
from app.modules.users.models import CompanyUser


@dataclass(frozen=True, slots=True)
class ReviewAssignmentError(Exception):
    code: str
    detail: str


async def _active_on_call_user_ids(
    database: AsyncSession,
    *,
    company_id: UUID,
    agent_id: UUID,
    policy_id: UUID | None,
    user_ids: tuple[UUID, ...],
    timezone: str,
    start_hour: int,
    end_hour: int,
    weekdays: tuple[int, ...],
    shifts: tuple[dict[str, object], ...],
    holiday_calendar: tuple[dict[str, object], ...],
) -> list[UUID]:
    now = utc_now()
    local_now = now.astimezone(ZoneInfo(timezone))
    holiday = next(
        (
            item
            for item in holiday_calendar
            if str(item.get("date")) == local_now.date().isoformat()
        ),
        None,
    )
    if holiday is not None and not bool(holiday.get("coverage_required", False)):
        return []
    scheduled_user_ids = (
        tuple(
            UUID(str(shift["user_id"]))
            for shift in shifts
            if local_now.weekday() in cast(list[int], shift["weekdays"])
            and int(str(shift["start_hour"])) <= local_now.hour
            and local_now.hour < int(str(shift["end_hour"]))
        )
        if shifts
        else (
            user_ids
            if (local_now.weekday() in weekdays and start_hour <= local_now.hour < end_hour)
            else ()
        )
    )
    if not scheduled_user_ids:
        return []
    handoffs = (
        list(
            await database.scalars(
                select(AgentDispatchReviewOnCallHandoff).where(
                    AgentDispatchReviewOnCallHandoff.company_id == company_id,
                    AgentDispatchReviewOnCallHandoff.agent_id == agent_id,
                    AgentDispatchReviewOnCallHandoff.policy_id == policy_id,
                    AgentDispatchReviewOnCallHandoff.status == "accepted",
                    AgentDispatchReviewOnCallHandoff.starts_at <= now,
                    AgentDispatchReviewOnCallHandoff.ends_at > now,
                )
            )
        )
        if policy_id is not None
        else []
    )
    replacement_by_user = {handoff.from_user_id: handoff.to_user_id for handoff in handoffs}
    candidate_ids = set(scheduled_user_ids) | set(replacement_by_user.values())
    active_members = set(
        await database.scalars(
            select(CompanyUser.user_id).where(
                CompanyUser.company_id == company_id,
                CompanyUser.user_id.in_(candidate_ids),
                CompanyUser.status == "active",
            )
        )
    )
    current_approvers = set(await company_approver_user_ids(database, company_id))
    absent_user_ids = (
        set(
            await database.scalars(
                select(AgentDispatchReviewOnCallException.user_id).where(
                    AgentDispatchReviewOnCallException.company_id == company_id,
                    AgentDispatchReviewOnCallException.agent_id == agent_id,
                    AgentDispatchReviewOnCallException.policy_id == policy_id,
                    AgentDispatchReviewOnCallException.status == "active",
                    AgentDispatchReviewOnCallException.starts_at <= now,
                    AgentDispatchReviewOnCallException.ends_at > now,
                )
            )
        )
        if policy_id is not None
        else set()
    )
    routed: list[UUID] = []
    for configured_user_id in scheduled_user_ids:
        effective_user_id = replacement_by_user.get(configured_user_id, configured_user_id)
        if (
            effective_user_id in active_members
            and effective_user_id in current_approvers
            and effective_user_id not in absent_user_ids
            and effective_user_id not in routed
        ):
            routed.append(effective_user_id)
    return routed


def _audit_assignment(
    database: AsyncSession,
    *,
    review: AgentDispatchReview,
    assignment: AgentDispatchReviewAssignment,
    actor_user_id: UUID,
    action: str,
) -> None:
    record_authorization_audit(
        database,
        company_id=review.company_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type="agent_dispatch_review_assignment",
        target_id=assignment.id,
        details={
            "agent_id": str(review.agent_id),
            "review_id": str(review.id),
            "source": assignment.source,
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=action,
            company_id=review.company_id,
            actor_user_id=actor_user_id,
            classification="internal",
            payload={
                "agent_id": str(review.agent_id),
                "review_id": str(review.id),
                "assignment_id": str(assignment.id),
            },
        ),
    )


async def current_review_assignment(
    database: AsyncSession, *, company_id: UUID, review_id: UUID, lock: bool = False
) -> AgentDispatchReviewAssignment | None:
    statement = select(AgentDispatchReviewAssignment).where(
        AgentDispatchReviewAssignment.company_id == company_id,
        AgentDispatchReviewAssignment.review_id == review_id,
        AgentDispatchReviewAssignment.ended_at.is_(None),
    )
    if lock:
        statement = statement.with_for_update()
    assignment: AgentDispatchReviewAssignment | None = await database.scalar(statement)
    return assignment


async def assign_review_for_sla(
    database: AsyncSession,
    *,
    review: AgentDispatchReview,
    policy_id: UUID | None,
    on_call_user_ids: tuple[UUID, ...],
    on_call_timezone: str,
    on_call_start_hour: int,
    on_call_end_hour: int,
    on_call_weekdays: tuple[int, ...],
    on_call_shifts: tuple[dict[str, object], ...],
    holiday_calendar: tuple[dict[str, object], ...],
    escalated: bool,
) -> AgentDispatchReviewAssignment | None:
    configured = await _active_on_call_user_ids(
        database,
        company_id=review.company_id,
        agent_id=review.agent_id,
        policy_id=policy_id,
        user_ids=on_call_user_ids,
        timezone=on_call_timezone,
        start_hour=on_call_start_hour,
        end_hour=on_call_end_hour,
        weekdays=on_call_weekdays,
        shifts=on_call_shifts,
        holiday_calendar=holiday_calendar,
    )
    candidates = configured or await company_approver_user_ids(database, review.company_id)
    if not candidates:
        candidates = [review.requested_by_user_id]
    current = await current_review_assignment(
        database, company_id=review.company_id, review_id=review.id, lock=True
    )
    if current is not None and (
        not escalated
        or current.acknowledged_at is not None
        or (len(candidates) < 2 and current.assigned_to_user_id in candidates)
    ):
        return current
    previous_id = current.id if current is not None else None
    source = "on_call" if configured else "fallback"
    if current is None:
        assigned_to = candidates[0]
        reason_code = "sla_breach"
        action = "agent.dispatch_review.assigned"
    else:
        current.status = "reassigned"
        current.ended_at = utc_now()
        assigned_to = (
            candidates[(candidates.index(current.assigned_to_user_id) + 1) % len(candidates)]
            if current.assigned_to_user_id in candidates
            else candidates[0]
        )
        reason_code = "sla_escalation_unacknowledged"
        action = "agent.dispatch_review.reassigned_automatically"
    assignment = AgentDispatchReviewAssignment(
        company_id=review.company_id,
        agent_id=review.agent_id,
        review_id=review.id,
        previous_assignment_id=previous_id,
        assigned_to_user_id=assigned_to,
        assigned_by_user_id=None,
        source=source,
        status="pending",
        reason_code=reason_code,
    )
    database.add(assignment)
    await database.flush()
    _audit_assignment(
        database,
        review=review,
        assignment=assignment,
        actor_user_id=review.requested_by_user_id,
        action=action,
    )
    return assignment


async def acknowledge_review_assignment(
    database: AsyncSession,
    *,
    company_id: UUID,
    agent_id: UUID,
    review_id: UUID,
    assignment_id: UUID,
    actor_user_id: UUID,
) -> AgentDispatchReviewAssignment:
    assignment = await database.scalar(
        select(AgentDispatchReviewAssignment)
        .where(
            AgentDispatchReviewAssignment.id == assignment_id,
            AgentDispatchReviewAssignment.company_id == company_id,
            AgentDispatchReviewAssignment.agent_id == agent_id,
            AgentDispatchReviewAssignment.review_id == review_id,
            AgentDispatchReviewAssignment.ended_at.is_(None),
        )
        .with_for_update()
    )
    if assignment is None:
        raise ReviewAssignmentError("assignment_not_found", "Atribuição ativa não encontrada.")
    if assignment.assigned_to_user_id != actor_user_id:
        raise ReviewAssignmentError(
            "assignment_forbidden", "Somente o responsável atual pode confirmar o recebimento."
        )
    if assignment.acknowledged_at is None:
        assignment.status = "acknowledged"
        assignment.acknowledged_by_user_id = actor_user_id
        assignment.acknowledged_at = utc_now()
        review = await database.get(AgentDispatchReview, review_id)
        if review is None:
            raise ReviewAssignmentError("review_not_found", "Revisão não encontrada.")
        _audit_assignment(
            database,
            review=review,
            assignment=assignment,
            actor_user_id=actor_user_id,
            action="agent.dispatch_review.assignment_acknowledged",
        )
    return assignment


async def reassign_review(
    database: AsyncSession,
    *,
    company_id: UUID,
    agent_id: UUID,
    review_id: UUID,
    assigned_to_user_id: UUID,
    actor_user_id: UUID,
) -> AgentDispatchReviewAssignment:
    if assigned_to_user_id not in await company_approver_user_ids(database, company_id):
        raise ReviewAssignmentError(
            "assignee_invalid",
            "O novo responsável deve ser um aprovador ativo desta empresa.",
        )
    review = await database.scalar(
        select(AgentDispatchReview).where(
            AgentDispatchReview.id == review_id,
            AgentDispatchReview.company_id == company_id,
            AgentDispatchReview.agent_id == agent_id,
        )
    )
    if review is None:
        raise ReviewAssignmentError("review_not_found", "Revisão não encontrada.")
    current = await current_review_assignment(
        database, company_id=company_id, review_id=review_id, lock=True
    )
    if current is not None and current.assigned_to_user_id == assigned_to_user_id:
        return current
    if current is not None:
        current.status = "reassigned"
        current.ended_at = utc_now()
    assignment = AgentDispatchReviewAssignment(
        company_id=company_id,
        agent_id=agent_id,
        review_id=review_id,
        previous_assignment_id=current.id if current is not None else None,
        assigned_to_user_id=assigned_to_user_id,
        assigned_by_user_id=actor_user_id,
        source="manual",
        status="pending",
        reason_code="manual_reassignment",
    )
    database.add(assignment)
    await database.flush()
    _audit_assignment(
        database,
        review=review,
        assignment=assignment,
        actor_user_id=actor_user_id,
        action="agent.dispatch_review.reassigned_manually",
    )
    return assignment
