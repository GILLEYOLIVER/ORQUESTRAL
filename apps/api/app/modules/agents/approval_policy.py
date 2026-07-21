from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.approval_policy_models import AgentApprovalPolicyVersion


@dataclass(frozen=True, slots=True)
class ApprovalPolicyDecision:
    allowed: bool
    requires_approval: bool
    policy_version_id: UUID | None
    policy_key: str | None
    reason: str
    approval_ttl_minutes: int = 30
    assigned_user_id: UUID | None = None


def _value_at_path(arguments: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = arguments
    for segment in path.split("."):
        if not isinstance(current, Mapping) or segment not in current:
            return False, None
        current = current[segment]
    return True, current


def _matches(policy: AgentApprovalPolicyVersion, arguments: Mapping[str, Any]) -> bool:
    if policy.amount_field:
        found, amount = _value_at_path(arguments, policy.amount_field)
        if not found or isinstance(amount, bool) or not isinstance(amount, int):
            return False
        if policy.min_amount_microunits is not None and amount < policy.min_amount_microunits:
            return False
        if policy.max_amount_microunits is not None and amount > policy.max_amount_microunits:
            return False
    if policy.currency:
        found, currency = _value_at_path(arguments, "currency")
        if not found or not isinstance(currency, str) or currency.upper() != policy.currency:
            return False
    for path, expected in policy.context_conditions.items():
        found, actual = _value_at_path(arguments, path)
        if not found or actual != expected:
            return False
    return True


def evaluate_published_policies(
    policies: Sequence[AgentApprovalPolicyVersion],
    *,
    arguments: Mapping[str, Any],
) -> ApprovalPolicyDecision:
    effect_precedence = {"allow": 0, "require_approval": 1, "deny": 2}
    ordered = sorted(
        (policy for policy in policies if policy.status == "published"),
        key=lambda policy: (
            policy.priority,
            effect_precedence.get(policy.effect, -1),
            policy.version,
        ),
        reverse=True,
    )
    matched = next((policy for policy in ordered if _matches(policy, arguments)), None)
    if matched is None:
        return ApprovalPolicyDecision(
            allowed=True,
            requires_approval=False,
            policy_version_id=None,
            policy_key=None,
            reason="Nenhuma política adicional corresponde a esta chamada.",
        )
    if matched.effect == "deny":
        return ApprovalPolicyDecision(
            allowed=False,
            requires_approval=False,
            policy_version_id=matched.id,
            policy_key=matched.policy_key,
            reason="A política empresarial bloqueia esta chamada.",
            approval_ttl_minutes=matched.approval_ttl_minutes,
            assigned_user_id=matched.assigned_user_id,
        )
    return ApprovalPolicyDecision(
        allowed=True,
        requires_approval=matched.effect == "require_approval",
        policy_version_id=matched.id,
        policy_key=matched.policy_key,
        reason=(
            "A política empresarial exige aprovação humana."
            if matched.effect == "require_approval"
            else "A política empresarial permite esta chamada dentro dos limites configurados."
        ),
        approval_ttl_minutes=matched.approval_ttl_minutes,
        assigned_user_id=matched.assigned_user_id,
    )


async def evaluate_agent_approval_policy(
    database: AsyncSession,
    *,
    company_id: UUID,
    agent_id: UUID,
    tool_key: str,
    arguments: Mapping[str, Any],
) -> ApprovalPolicyDecision:
    policies = (
        await database.scalars(
            select(AgentApprovalPolicyVersion).where(
                AgentApprovalPolicyVersion.company_id == company_id,
                AgentApprovalPolicyVersion.agent_id == agent_id,
                AgentApprovalPolicyVersion.status == "published",
                or_(
                    AgentApprovalPolicyVersion.tool_key.is_(None),
                    AgentApprovalPolicyVersion.tool_key == tool_key,
                ),
            )
        )
    ).all()
    return evaluate_published_policies(policies, arguments=arguments)
