from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import Settings
from app.core.resources import create_resources
from app.core.security import hash_password
from app.main import create_app
from app.modules.agents.dispatch_execution import execute_ready_agent_dispatches
from app.modules.agents.models import AgentBudget, AgentRun, AgentRunStep
from app.modules.agents.review_sla_service import maintain_agent_dispatch_review_sla
from app.modules.agents.runtime_models import (
    AgentDispatchReview,
    AgentExecutionSchedule,
    AgentRuntimeDispatch,
)
from app.modules.agents.runtime_service import maintain_agent_runtime
from app.modules.authorization.models import AuthorizationAuditEvent
from app.modules.authorization.service import ensure_company_system_roles
from app.modules.companies.models import Company
from app.modules.events.models import OutboxEvent
from app.modules.users.models import CompanyUser, User


@dataclass(frozen=True, slots=True)
class DispatchIdentity:
    company_ids: tuple[UUID, UUID]
    user_ids: tuple[UUID, UUID]
    emails: tuple[str, str]
    password: str


async def _seed(settings: Settings) -> DispatchIdentity:
    resources = create_resources(settings)
    suffix = uuid4().hex[:10]
    password = "Dispatch-Integration-2026!"  # noqa: S105
    try:
        async with resources.sessions() as database:
            companies = tuple(
                Company(
                    legal_name=f"Executor Governado {label} {suffix} Ltda.",
                    trade_name=f"Executor Governado {label} {suffix}",
                    document_number=f"DGE{label}{suffix}",
                    slug=f"executor-governado-{label.lower()}-{suffix}",
                    status="active",
                )
                for label in ("A", "B")
            )
            users = tuple(
                User(
                    name=f"Administrador Executor {label}",
                    email=f"executor-{label.lower()}-{suffix}@example.com",
                    password_hash=hash_password(password),
                    status="active",
                )
                for label in ("A", "B")
            )
            database.add_all((*companies, *users))
            await database.flush()
            for company, user in zip(companies, users, strict=True):
                owner, _ = await ensure_company_system_roles(database, company.id)
                database.add(
                    CompanyUser(
                        company_id=company.id,
                        user_id=user.id,
                        role_id=owner.id,
                        status="active",
                        is_owner=True,
                    )
                )
            await database.commit()
            return DispatchIdentity(
                company_ids=(companies[0].id, companies[1].id),
                user_ids=(users[0].id, users[1].id),
                emails=(users[0].email, users[1].email),
                password=password,
            )
    finally:
        await resources.close()


async def _remove(settings: Settings, identity: DispatchIdentity) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            await database.execute(
                delete(OutboxEvent).where(OutboxEvent.company_id.in_(identity.company_ids))
            )
            await database.execute(delete(Company).where(Company.id.in_(identity.company_ids)))
            await database.execute(delete(User).where(User.email.in_(identity.emails)))
            await database.commit()
    finally:
        await resources.close()


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _assert_persisted_trace(
    settings: Settings,
    *,
    company_id: UUID,
    foreign_company_id: UUID,
    dispatch_id: UUID,
    run_id: UUID,
) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            run = await database.scalar(
                select(AgentRun).where(
                    AgentRun.id == run_id,
                    AgentRun.company_id == company_id,
                )
            )
            assert run is not None
            assert run.execution_mode == "shadow"
            assert run.status == "simulated"
            assert run.completed_tool_keys == ["orkestral.company.summary"]

            steps = list(
                await database.scalars(
                    select(AgentRunStep)
                    .where(
                        AgentRunStep.agent_run_id == run_id,
                        AgentRunStep.company_id == company_id,
                    )
                    .order_by(AgentRunStep.sequence)
                )
            )
            assert [step.step_type for step in steps] == ["runtime", "tool"]
            assert [step.status for step in steps] == ["simulated", "simulated"]
            assert steps[1].input_fingerprint
            assert steps[1].output_fingerprint is None

            audit = await database.scalar(
                select(AuthorizationAuditEvent).where(
                    AuthorizationAuditEvent.company_id == company_id,
                    AuthorizationAuditEvent.action == "agent.dispatch.simulated",
                    AuthorizationAuditEvent.target_type == "agent_runtime_dispatch",
                    AuthorizationAuditEvent.target_id == str(dispatch_id),
                )
            )
            assert audit is not None

            events = list(
                await database.scalars(
                    select(OutboxEvent).where(OutboxEvent.company_id == company_id)
                )
            )
            assert any(str(dispatch_id) in str(event.payload) for event in events)

            assert (
                await database.scalar(
                    select(AgentRun).where(
                        AgentRun.id == run_id,
                        AgentRun.company_id == foreign_company_id,
                    )
                )
                is None
            )
    finally:
        await resources.close()


async def _make_schedule_due(settings: Settings, schedule_id: UUID) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            schedule = await database.get(AgentExecutionSchedule, schedule_id)
            assert schedule is not None
            schedule.next_run_at = datetime.now(UTC) - timedelta(minutes=1)
            await database.commit()
    finally:
        await resources.close()


async def _make_dispatch_stale(settings: Settings, dispatch_id: UUID) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            dispatch = await database.get(AgentRuntimeDispatch, dispatch_id)
            assert dispatch is not None
            run = await database.get(AgentRun, dispatch.agent_run_id)
            assert run is not None
            budget = await database.scalar(
                select(AgentBudget).where(
                    AgentBudget.company_id == dispatch.company_id,
                    AgentBudget.agent_id == dispatch.agent_id,
                )
            )
            assert budget is not None
            interrupted_at = datetime.now(UTC) - timedelta(minutes=20)
            dispatch.status = "processing"
            dispatch.started_at = interrupted_at
            dispatch.finished_at = None
            dispatch.reason_code = None
            dispatch.error_code = None
            dispatch.reserved_microunits = 123
            run.status = "running"
            run.started_at = interrupted_at
            run.finished_at = None
            run.error_code = None
            budget.reserved_microunits += 123
            await database.commit()
    finally:
        await resources.close()


async def _assert_interrupted_dispatch_reconciled(
    settings: Settings, *, dispatch_id: UUID, run_id: UUID
) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            dispatch = await database.get(AgentRuntimeDispatch, dispatch_id)
            run = await database.get(AgentRun, run_id)
            assert dispatch is not None
            assert run is not None
            assert dispatch.status == "failed"
            assert dispatch.error_code == "execution_interrupted_manual_review"
            assert dispatch.reserved_microunits == 0
            assert run.status == "failed"
            assert run.error_code == "execution_interrupted_manual_review"
            budget = await database.scalar(
                select(AgentBudget).where(
                    AgentBudget.company_id == dispatch.company_id,
                    AgentBudget.agent_id == dispatch.agent_id,
                )
            )
            assert budget is not None
            assert budget.reserved_microunits == 0
            reconciliation_step = await database.scalar(
                select(AgentRunStep).where(
                    AgentRunStep.agent_run_id == run_id,
                    AgentRunStep.summary_code == "dispatch.interrupted.manual_review",
                )
            )
            assert reconciliation_step is not None
            audit = await database.scalar(
                select(AuthorizationAuditEvent).where(
                    AuthorizationAuditEvent.company_id == dispatch.company_id,
                    AuthorizationAuditEvent.action == "agent.dispatch.interrupted",
                    AuthorizationAuditEvent.target_id == str(dispatch_id),
                )
            )
            assert audit is not None
            event = await database.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.company_id == dispatch.company_id,
                    OutboxEvent.event_type == "agent.dispatch.interrupted",
                    OutboxEvent.payload["dispatch_id"].as_string()
                    == str(dispatch_id),
                )
            )
            assert event is not None
            assert event.payload["retry_policy"] == "manual_review_required"
    finally:
        await resources.close()


async def _make_review_overdue(settings: Settings, review_id: UUID) -> None:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            review = await database.get(AgentDispatchReview, review_id)
            assert review is not None
            review.created_at = datetime.now(UTC) - timedelta(minutes=45)
            await database.commit()
    finally:
        await resources.close()


@pytest.mark.integration
def test_governed_dispatch_executes_in_shadow_with_trace_and_tenant_isolation() -> None:
    settings = Settings(app_env="testing")
    identity = asyncio.run(_seed(settings))
    try:
        with TestClient(create_app(settings)) as client:
            headers_a = _login(client, identity.emails[0], identity.password)
            headers_b = _login(client, identity.emails[1], identity.password)

            created = client.post(
                "/agents",
                headers=headers_b,
                json={
                    "name": "Executor Governado",
                    "instructions": "Consulte somente informações autorizadas da empresa atual.",
                },
            )
            assert created.status_code == 201
            agent_id = created.json()["id"]

            configured_tools = client.put(
                f"/agents/{agent_id}/tools",
                headers=headers_b,
                json={"tool_keys": ["orkestral.company.summary"]},
            )
            assert configured_tools.status_code == 200

            policy = client.post(
                f"/agents/{agent_id}/approval-policies",
                headers=headers_b,
                json={
                    "policy_key": "summary-shadow-allow",
                    "name": "Consulta segura em modo sombra",
                    "effect": "allow",
                    "tool_key": "orkestral.company.summary",
                    "priority": 500,
                },
            )
            assert policy.status_code == 201
            published_policy = client.post(
                f"/agents/{agent_id}/approval-policies/{policy.json()['id']}/publish",
                headers=headers_b,
            )
            assert published_policy.status_code == 200

            budget = client.put(
                f"/agents/{agent_id}/budget",
                headers=headers_b,
                json={"limit_microunits": 1_000_000, "hard_limit": True},
            )
            assert budget.status_code == 200

            schedule = client.post(
                f"/agents/{agent_id}/schedules",
                headers=headers_b,
                json={
                    "schedule_key": "summary-shadow",
                    "name": "Resumo seguro em modo sombra",
                    "objective": "Gerar um resumo autorizado da empresa para validação.",
                    "cadence_minutes": 60,
                    "required_tool_keys": ["orkestral.company.summary"],
                    "tool_arguments": {"orkestral.company.summary": {}},
                    "execution_mode": "shadow",
                    "canary_percentage": 0,
                    "first_run_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
                },
            )
            assert schedule.status_code == 201
            schedule_id = schedule.json()["id"]
            published_schedule = client.post(
                f"/agents/{agent_id}/schedules/{schedule_id}/publish",
                headers=headers_b,
            )
            assert published_schedule.status_code == 200
            asyncio.run(_make_schedule_due(settings, UUID(schedule_id)))

            assert (
                client.get(f"/agents/{agent_id}/runtime-dispatches", headers=headers_a).status_code
                == 404
            )

            runtime_result = asyncio.run(maintain_agent_runtime(settings=settings, limit=20))
            assert any(value > 0 for value in runtime_result.values())
            execution_result = asyncio.run(
                execute_ready_agent_dispatches(settings=settings, limit=20)
            )
            observed_dispatches = client.get(
                f"/agents/{agent_id}/runtime-dispatches", headers=headers_b
            )
            assert execution_result["claimed"] == 1, (
                runtime_result,
                execution_result,
                [
                    (item["status"], item["reason_code"], item["error_code"])
                    for item in observed_dispatches.json()
                ],
            )
            assert execution_result["simulated"] == 1
            assert execution_result["failed"] == 0

            dispatches = client.get(
                f"/agents/{agent_id}/runtime-dispatches", headers=headers_b
            )
            assert dispatches.status_code == 200
            dispatch = next(
                item for item in dispatches.json() if item["schedule_id"] == schedule_id
            )
            assert dispatch["status"] == "simulated"
            assert dispatch["execution_mode"] == "shadow"
            assert dispatch["attempt_count"] == 1
            assert dispatch["agent_run_id"]

            asyncio.run(
                _assert_persisted_trace(
                    settings,
                    company_id=identity.company_ids[1],
                    foreign_company_id=identity.company_ids[0],
                    dispatch_id=UUID(dispatch["id"]),
                    run_id=UUID(dispatch["agent_run_id"]),
                )
            )
            dispatch_id = UUID(dispatch["id"])
            run_id = UUID(dispatch["agent_run_id"])
            asyncio.run(_make_dispatch_stale(settings, dispatch_id))
            reconciliation_result = asyncio.run(
                execute_ready_agent_dispatches(settings=settings, limit=20)
            )
            assert reconciliation_result["reconciled"] == 1
            assert reconciliation_result["claimed"] == 0
            assert reconciliation_result["failed"] == 1
            asyncio.run(
                _assert_interrupted_dispatch_reconciled(
                    settings,
                    dispatch_id=dispatch_id,
                    run_id=run_id,
                )
            )

            review_key = str(uuid4())
            review_payload = {
                "decision": "retry",
                "reason": "A interrupção foi analisada e a repetição controlada é necessária.",
                "idempotency_key": review_key,
            }
            foreign_review = client.post(
                f"/agents/{agent_id}/runtime-dispatches/{dispatch_id}/reviews",
                headers=headers_a,
                json=review_payload,
            )
            assert foreign_review.status_code == 404

            review = client.post(
                f"/agents/{agent_id}/runtime-dispatches/{dispatch_id}/reviews",
                headers=headers_b,
                json=review_payload,
            )
            assert review.status_code == 201
            assert review.json()["status"] == "pending_approval"
            assert review.json()["replacement_dispatch_id"] is None

            foreign_policy = client.post(
                f"/agents/{agent_id}/runtime-dispatch-review-sla-policies",
                headers=headers_a,
                json={
                    "name": "SLA crítico",
                    "sla_minutes": 20,
                    "escalation_minutes": 40,
                },
            )
            assert foreign_policy.status_code == 404
            policy = client.post(
                f"/agents/{agent_id}/runtime-dispatch-review-sla-policies",
                headers=headers_b,
                json={
                    "name": "SLA crítico",
                    "sla_minutes": 20,
                    "escalation_minutes": 40,
                },
            )
            assert policy.status_code == 201
            assert policy.json()["status"] == "draft"
            published_policy = client.post(
                f"/agents/{agent_id}/runtime-dispatch-review-sla-policies/"
                f"{policy.json()['id']}/publish",
                headers=headers_b,
            )
            assert published_policy.status_code == 200
            assert published_policy.json()["status"] == "published"

            initial_summary = client.get(
                f"/agents/{agent_id}/runtime-dispatch-reviews/summary",
                headers=headers_b,
            )
            assert initial_summary.status_code == 200
            assert initial_summary.json()["pending"] == 1
            assert initial_summary.json()["overdue"] == 0
            assert initial_summary.json()["sla_minutes"] == 20
            assert initial_summary.json()["escalation_minutes"] == 40
            assert initial_summary.json()["policy_version"] == 1

            asyncio.run(_make_review_overdue(settings, UUID(review.json()["id"])))
            first_sla_result = asyncio.run(
                maintain_agent_dispatch_review_sla(settings=settings)
            )
            second_sla_result = asyncio.run(
                maintain_agent_dispatch_review_sla(settings=settings)
            )
            assert first_sla_result["review_breaches"] == 1
            assert first_sla_result["notifications"] >= 1
            assert second_sla_result == {"review_breaches": 0, "notifications": 0}

            overdue_summary = client.get(
                f"/agents/{agent_id}/runtime-dispatch-reviews/summary",
                headers=headers_b,
            )
            assert overdue_summary.status_code == 200
            assert overdue_summary.json()["overdue"] == 1
            assert overdue_summary.json()["oldest_pending_minutes"] >= 44
            assert (
                client.get(
                    f"/agents/{agent_id}/runtime-dispatch-reviews/summary",
                    headers=headers_a,
                ).status_code
                == 404
            )

            replayed_review = client.post(
                f"/agents/{agent_id}/runtime-dispatches/{dispatch_id}/reviews",
                headers=headers_b,
                json=review_payload,
            )
            assert replayed_review.status_code == 201
            assert replayed_review.json()["id"] == review.json()["id"]

            conflicting_review = client.post(
                f"/agents/{agent_id}/runtime-dispatches/{dispatch_id}/reviews",
                headers=headers_b,
                json={**review_payload, "idempotency_key": str(uuid4())},
            )
            assert conflicting_review.status_code == 409

            approval_key = str(uuid4())
            approved = client.post(
                f"/agents/{agent_id}/runtime-dispatch-reviews/{review.json()['id']}/approve-retry",
                headers=headers_b,
                json={"idempotency_key": approval_key},
            )
            assert approved.status_code == 200
            assert approved.json()["status"] == "approved"
            replacement_id = approved.json()["replacement_dispatch_id"]
            assert replacement_id

            replayed_approval = client.post(
                f"/agents/{agent_id}/runtime-dispatch-reviews/{review.json()['id']}/approve-retry",
                headers=headers_b,
                json={"idempotency_key": approval_key},
            )
            assert replayed_approval.status_code == 200
            assert replayed_approval.json()["replacement_dispatch_id"] == replacement_id

            replacement_dispatches = client.get(
                f"/agents/{agent_id}/runtime-dispatches", headers=headers_b
            )
            replacement = next(
                item for item in replacement_dispatches.json() if item["id"] == replacement_id
            )
            assert replacement["source_type"] == "retry"
            assert replacement["retry_of_dispatch_id"] == str(dispatch_id)
            assert replacement["status"] == "ready"

            retry_result = asyncio.run(
                execute_ready_agent_dispatches(settings=settings, limit=20)
            )
            assert retry_result["claimed"] == 1
            assert retry_result["simulated"] == 1
    finally:
        asyncio.run(_remove(settings, identity))
