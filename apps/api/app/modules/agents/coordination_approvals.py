from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utc_now
from app.modules.agents.approval_policy_models import (
    AgentApprovalPolicyStage,
    AgentApprovalPolicyStageApprover,
)
from app.modules.agents.coordination_models import (
    AgentDelegation,
    AgentDelegationApproval,
    AgentDelegationApprovalVote,
    AgentDelegationPayload,
)
from app.modules.notifications.models import ApprovalRequest
from app.modules.notifications.service import create_notification, is_company_approver


class ApprovalStageAccessError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StageVoteProgress:
    approved_votes: int
    stage_approved: bool
    rejected: bool


@dataclass(frozen=True, slots=True)
class DelegationApprovalOutcome:
    linked: bool
    pending: bool
    resumed_delegation_id: UUID | None = None
    stage_order: int | None = None
    approved_votes: int | None = None
    quorum: int | None = None


def evaluate_stage_vote(
    *, quorum: int, existing_approved_votes: int, actor_has_voted: bool, decision: str
) -> StageVoteProgress:
    if actor_has_voted:
        raise ValueError("Você já registrou uma decisão nesta etapa.")
    if decision == "rejected":
        return StageVoteProgress(existing_approved_votes, False, True)
    approved_votes = existing_approved_votes + 1
    return StageVoteProgress(approved_votes, approved_votes >= quorum, False)


async def _reject_delegation(
    database: AsyncSession,
    *,
    linked: AgentDelegationApproval,
    delegation: AgentDelegation,
    company_id: UUID,
    actor_user_id: UUID,
) -> None:
    now = utc_now()
    linked.status = "rejected"
    linked.decided_by_user_id = actor_user_id
    linked.decided_at = now
    linked.encrypted_arguments = None
    delegation.status = "cancelled"
    delegation.last_error_code = "human_rejected"
    delegation.finished_at = now
    delegation.claimed_by = None
    delegation.lease_expires_at = None
    payload = await database.scalar(
        select(AgentDelegationPayload).where(
            AgentDelegationPayload.delegation_id == delegation.id,
            AgentDelegationPayload.company_id == company_id,
        )
    )
    if payload is not None:
        payload.encrypted_objective = None
        payload.destroyed_at = now


async def _stage_approver_ids(
    database: AsyncSession, *, company_id: UUID, stage_id: UUID
) -> list[UUID]:
    return list(
        await database.scalars(
            select(AgentApprovalPolicyStageApprover.user_id).where(
                AgentApprovalPolicyStageApprover.company_id == company_id,
                AgentApprovalPolicyStageApprover.stage_id == stage_id,
            )
        )
    )


async def decide_delegation_approval(
    database: AsyncSession,
    *,
    approval_request_id: UUID,
    company_id: UUID,
    actor_user_id: UUID,
    decision: str,
) -> DelegationApprovalOutcome:
    linked = await database.scalar(
        select(AgentDelegationApproval)
        .where(
            AgentDelegationApproval.approval_request_id == approval_request_id,
            AgentDelegationApproval.company_id == company_id,
        )
        .with_for_update()
    )
    if linked is None:
        return DelegationApprovalOutcome(linked=False, pending=False)
    if linked.status != "pending":
        raise ValueError("A aprovação da delegação já foi decidida.")
    delegation = await database.scalar(
        select(AgentDelegation)
        .where(
            AgentDelegation.id == linked.delegation_id,
            AgentDelegation.company_id == company_id,
        )
        .with_for_update()
    )
    if delegation is None or delegation.status != "awaiting_approval":
        raise ValueError("A delegação vinculada não está aguardando aprovação.")

    if linked.current_policy_stage_id is None:
        if decision == "approved":
            linked.status = "approved"
            linked.decided_by_user_id = actor_user_id
            linked.decided_at = utc_now()
            delegation.status = "queued"
            delegation.claimed_by = None
            delegation.lease_expires_at = None
            return DelegationApprovalOutcome(True, False, delegation.id)
        await _reject_delegation(
            database,
            linked=linked,
            delegation=delegation,
            company_id=company_id,
            actor_user_id=actor_user_id,
        )
        return DelegationApprovalOutcome(linked=True, pending=False)

    stage = await database.scalar(
        select(AgentApprovalPolicyStage).where(
            AgentApprovalPolicyStage.id == linked.current_policy_stage_id,
            AgentApprovalPolicyStage.company_id == company_id,
            AgentApprovalPolicyStage.policy_version_id == linked.policy_version_id,
        )
    )
    if stage is None:
        raise ValueError("A etapa de aprovação vinculada não está disponível.")
    approver_ids = await _stage_approver_ids(database, company_id=company_id, stage_id=stage.id)
    if actor_user_id not in approver_ids or not await is_company_approver(
        database, company_id=company_id, user_id=actor_user_id
    ):
        raise ApprovalStageAccessError("Você não participa desta etapa de aprovação.")
    actor_has_voted = bool(
        await database.scalar(
            select(func.count(AgentDelegationApprovalVote.id)).where(
                AgentDelegationApprovalVote.company_id == company_id,
                AgentDelegationApprovalVote.delegation_approval_id == linked.id,
                AgentDelegationApprovalVote.policy_stage_id == stage.id,
                AgentDelegationApprovalVote.user_id == actor_user_id,
            )
        )
    )
    approved_votes = int(
        await database.scalar(
            select(func.count(AgentDelegationApprovalVote.id)).where(
                AgentDelegationApprovalVote.company_id == company_id,
                AgentDelegationApprovalVote.delegation_approval_id == linked.id,
                AgentDelegationApprovalVote.policy_stage_id == stage.id,
                AgentDelegationApprovalVote.decision == "approved",
            )
        )
        or 0
    )
    progress = evaluate_stage_vote(
        quorum=stage.quorum,
        existing_approved_votes=approved_votes,
        actor_has_voted=actor_has_voted,
        decision=decision,
    )
    database.add(
        AgentDelegationApprovalVote(
            company_id=company_id,
            delegation_approval_id=linked.id,
            policy_stage_id=stage.id,
            user_id=actor_user_id,
            decision=decision,
        )
    )
    if progress.rejected:
        await _reject_delegation(
            database,
            linked=linked,
            delegation=delegation,
            company_id=company_id,
            actor_user_id=actor_user_id,
        )
        return DelegationApprovalOutcome(linked=True, pending=False)

    request = await database.get(ApprovalRequest, approval_request_id)
    if request is None or request.company_id != company_id:
        raise ValueError("A solicitação central vinculada não está disponível.")
    request.context = {
        **request.context,
        "approval_stage_order": stage.stage_order,
        "approval_stage_name": stage.name,
        "approval_stage_quorum": stage.quorum,
        "approval_stage_approved_votes": progress.approved_votes,
    }
    if not progress.stage_approved:
        return DelegationApprovalOutcome(
            True,
            True,
            stage_order=stage.stage_order,
            approved_votes=progress.approved_votes,
            quorum=stage.quorum,
        )

    next_stage = await database.scalar(
        select(AgentApprovalPolicyStage)
        .where(
            AgentApprovalPolicyStage.company_id == company_id,
            AgentApprovalPolicyStage.policy_version_id == linked.policy_version_id,
            AgentApprovalPolicyStage.stage_order > stage.stage_order,
        )
        .order_by(AgentApprovalPolicyStage.stage_order)
        .limit(1)
    )
    if next_stage is not None:
        next_approver_ids = await _stage_approver_ids(
            database, company_id=company_id, stage_id=next_stage.id
        )
        linked.current_policy_stage_id = next_stage.id
        request.assigned_user_id = (
            next_approver_ids[0] if next_stage.quorum == 1 and len(next_approver_ids) == 1 else None
        )
        request.context = {
            **request.context,
            "approval_stage_order": next_stage.stage_order,
            "approval_stage_name": next_stage.name,
            "approval_stage_quorum": next_stage.quorum,
            "approval_stage_approved_votes": 0,
        }
        for recipient_user_id in next_approver_ids:
            await create_notification(
                database,
                company_id=company_id,
                recipient_user_id=recipient_user_id,
                event_type="approval.stage_started",
                title="Nova etapa de aprovação",
                message=request.title,
                severity="warning",
                resource_type="approval_request",
                resource_id=request.id,
                data={"source_type": request.source_type},
            )
        return DelegationApprovalOutcome(
            True,
            True,
            stage_order=next_stage.stage_order,
            approved_votes=0,
            quorum=next_stage.quorum,
        )

    linked.status = "approved"
    linked.decided_by_user_id = actor_user_id
    linked.decided_at = utc_now()
    delegation.status = "queued"
    delegation.claimed_by = None
    delegation.lease_expires_at = None
    return DelegationApprovalOutcome(True, False, delegation.id)
