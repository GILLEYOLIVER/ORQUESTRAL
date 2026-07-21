from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.execution_context import (
    ExecutionContext,
    bind_execution_context,
    get_execution_context,
    require_execution_context,
)
from app.modules.authorization.policy_schemas import (
    PolicyRequest,
    PolicyResource,
    PolicySubject,
)
from app.modules.authorization.policy_service import evaluate_policy


def _request(**overrides: object) -> PolicyRequest:
    company_id = uuid4()
    values: dict[str, object] = {
        "subject": PolicySubject(
            user_id=uuid4(),
            company_id=company_id,
            permissions=frozenset({"crm.contacts.view"}),
        ),
        "resource": PolicyResource(company_id=company_id, resource_type="crm.contact"),
        "action": "view",
        "required_permission": "crm.contacts.view",
        "requested_fields": ("name", "email"),
        "correlation_id": uuid4(),
    }
    values.update(overrides)
    return PolicyRequest.model_validate(values)


def test_policy_denies_cross_tenant_access_without_platform_scope() -> None:
    request = _request(resource=PolicyResource(company_id=uuid4(), resource_type="crm.contact"))
    decision = evaluate_policy(request)
    assert decision.outcome == "deny"
    assert decision.reason_code == "tenant_mismatch"


def test_policy_denies_missing_permission_even_for_owner() -> None:
    company_id = uuid4()
    request = _request(
        subject=PolicySubject(company_id=company_id, is_owner=True),
        resource=PolicyResource(company_id=company_id, resource_type="crm.contact"),
    )
    decision = evaluate_policy(request)
    assert decision.outcome == "deny"
    assert decision.reason_code == "missing_permission"


def test_policy_masks_restricted_fields_on_read() -> None:
    request = _request(
        resource=PolicyResource(
            company_id=_request().subject.company_id,
            resource_type="hr.employee",
        )
    )
    company_id = request.resource.company_id
    request = _request(
        subject=PolicySubject(
            company_id=company_id,
            permissions=frozenset({"hr.view"}),
        ),
        resource=PolicyResource(
            company_id=company_id,
            resource_type="hr.employee",
            field_permissions={"salary": frozenset({"hr.compensation.view"})},
        ),
        required_permission="hr.view",
        requested_fields=("name", "salary"),
    )
    decision = evaluate_policy(request)
    assert decision.outcome == "allow"
    assert decision.allowed_fields == ("name",)
    assert decision.denied_fields == ("salary",)


def test_policy_requires_approval_for_high_risk_mutation() -> None:
    company_id = uuid4()
    request = _request(
        subject=PolicySubject(
            company_id=company_id,
            permissions=frozenset({"workflows.configure"}),
        ),
        resource=PolicyResource(company_id=company_id, resource_type="workflow"),
        action="execute",
        required_permission="workflows.configure",
        risk_level="high",
    )
    decision = evaluate_policy(request)
    assert decision.outcome == "require_approval"
    assert decision.allowed is False
    assert decision.requires_approval is True


def test_execution_context_roundtrip_and_reset() -> None:
    context = ExecutionContext(
        company_id=uuid4(),
        actor_user_id=uuid4(),
        correlation_id=uuid4(),
        source="unit-test",
        environment="testing",
    )
    restored = ExecutionContext.from_job_payload(context.to_job_payload())
    assert restored == context
    assert get_execution_context() is None
    with bind_execution_context(restored):
        assert require_execution_context() == context
    assert get_execution_context() is None
    with pytest.raises(RuntimeError, match="sem contexto"):
        require_execution_context()
