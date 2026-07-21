from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utc_now
from app.modules.agents.coordination_models import (
    AgentDelegation,
    AgentDelegationApproval,
    AgentDelegationPayload,
)


async def decide_delegation_approval(
    database: AsyncSession,
    *,
    approval_request_id: UUID,
    company_id: UUID,
    actor_user_id: UUID,
    decision: str,
) -> UUID | None:
    linked = await database.scalar(
        select(AgentDelegationApproval)
        .where(
            AgentDelegationApproval.approval_request_id == approval_request_id,
            AgentDelegationApproval.company_id == company_id,
        )
        .with_for_update()
    )
    if linked is None:
        return None
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
    now = utc_now()
    linked.decided_by_user_id = actor_user_id
    linked.decided_at = now
    if decision == "approved":
        linked.status = "approved"
        delegation.status = "queued"
        delegation.claimed_by = None
        delegation.lease_expires_at = None
        return delegation.id
    linked.status = "rejected"
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
    return None
