from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.authorization.policy_models import PolicyDecisionRecord
from app.modules.authorization.policy_schemas import PolicyDecision, PolicyRequest
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event

POLICY_VERSION = "2026-07-21.1"
READ_ACTIONS = frozenset({"view", "list"})


def _decision(
    *,
    outcome: str,
    reason_code: str,
    allowed_fields: tuple[str, ...] = (),
    denied_fields: tuple[str, ...] = (),
) -> PolicyDecision:
    return PolicyDecision(
        outcome=outcome,
        allowed=outcome == "allow",
        requires_approval=outcome == "require_approval",
        reason_code=reason_code,
        allowed_fields=allowed_fields,
        denied_fields=denied_fields,
        policy_version=POLICY_VERSION,
    )


def evaluate_policy(request: PolicyRequest) -> PolicyDecision:
    subject = request.subject
    resource = request.resource
    platform_scope = subject.is_platform_admin and request.allow_platform_scope

    if subject.company_id != resource.company_id and not platform_scope:
        return _decision(
            outcome="deny",
            reason_code="tenant_mismatch",
            denied_fields=request.requested_fields,
        )

    if request.required_permission and request.required_permission not in subject.permissions:
        return _decision(
            outcome="deny",
            reason_code="missing_permission",
            denied_fields=request.requested_fields,
        )

    allowed_fields: list[str] = []
    denied_fields: list[str] = []
    for field_name in request.requested_fields:
        required = resource.field_permissions.get(field_name, frozenset())
        if required and not required <= subject.permissions:
            denied_fields.append(field_name)
        else:
            allowed_fields.append(field_name)

    if denied_fields and request.action not in READ_ACTIONS:
        return _decision(
            outcome="deny",
            reason_code="field_access_denied",
            allowed_fields=tuple(allowed_fields),
            denied_fields=tuple(denied_fields),
        )

    if request.risk_level in {"high", "critical"} and request.action not in READ_ACTIONS:
        return _decision(
            outcome="require_approval",
            reason_code="approval_required",
            allowed_fields=tuple(allowed_fields),
            denied_fields=tuple(denied_fields),
        )

    reason_code = "partial_field_access" if denied_fields else "allowed"
    return _decision(
        outcome="allow",
        reason_code=reason_code,
        allowed_fields=tuple(allowed_fields),
        denied_fields=tuple(denied_fields),
    )


async def evaluate_and_record_policy(
    database: AsyncSession, request: PolicyRequest
) -> PolicyDecision:
    decision = evaluate_policy(request)
    database.add(
        PolicyDecisionRecord(
            company_id=request.subject.company_id,
            subject_user_id=request.subject.user_id,
            correlation_id=request.correlation_id,
            resource_type=request.resource.resource_type,
            resource_id=request.resource.resource_id,
            action=request.action,
            required_permission=request.required_permission,
            outcome=decision.outcome,
            reason_code=decision.reason_code,
            requested_fields=list(request.requested_fields),
            allowed_fields=list(decision.allowed_fields),
            denied_fields=list(decision.denied_fields),
            risk_level=request.risk_level,
            policy_version=decision.policy_version,
        )
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="security.policy.evaluated",
            company_id=request.subject.company_id,
            actor_user_id=request.subject.user_id,
            correlation_id=request.correlation_id,
            classification="internal",
            payload={
                "resource_type": request.resource.resource_type,
                "action": request.action,
                "outcome": decision.outcome,
                "reason_code": decision.reason_code,
                "policy_version": decision.policy_version,
            },
        ),
    )
    await database.flush()
    return decision
