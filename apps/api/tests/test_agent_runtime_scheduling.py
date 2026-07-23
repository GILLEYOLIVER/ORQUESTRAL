from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app
from app.modules.agents.runtime_schemas import AgentScheduleCreate, AgentTriggerCreate
from app.modules.agents.runtime_service import next_schedule_time, objective_fingerprint


def test_objective_fingerprint_is_tenant_scoped_and_hides_content() -> None:
    company_a = uuid4()
    company_b = uuid4()
    agent_id = uuid4()
    objective = "SEGREDO-OPERACIONAL-NAO-PERSISTIR"
    first = objective_fingerprint(
        "strong-development-key", company_id=company_a, agent_id=agent_id, objective=objective
    )
    repeated = objective_fingerprint(
        "strong-development-key", company_id=company_a, agent_id=agent_id, objective=objective
    )
    other_tenant = objective_fingerprint(
        "strong-development-key", company_id=company_b, agent_id=agent_id, objective=objective
    )
    assert first == repeated
    assert first != other_tenant
    assert objective not in first


def test_next_schedule_time_is_deterministic() -> None:
    now = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    assert next_schedule_time(now, 15) == now + timedelta(minutes=15)


def test_runtime_schemas_reject_duplicate_tools_and_invalid_ranges() -> None:
    with pytest.raises(ValidationError):
        AgentScheduleCreate(
            schedule_key="follow-up",
            name="Acompanhamento",
            objective="Acompanhar oportunidades paradas",
            cadence_minutes=60,
            required_tool_keys=["crm.contact.view", "CRM.CONTACT.VIEW"],
        )
    with pytest.raises(ValidationError):
        AgentTriggerCreate(
            trigger_key="lead-created",
            name="Qualificar lead",
            event_type="lead.created",
            min_event_version=3,
            max_event_version=2,
            objective="Qualificar o lead com segurança",
        )


def test_agent_runtime_endpoints_require_authentication() -> None:
    with TestClient(create_app(Settings(app_env="testing"))) as client:
        assert client.get(f"/agents/{uuid4()}/schedules").status_code == 401
        assert client.get(f"/agents/{uuid4()}/event-triggers").status_code == 401
        assert client.get("/agents/runtime/credential-catalog").status_code == 401
