from __future__ import annotations

import asyncio
import json
from time import perf_counter
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import utc_now
from app.modules.billing.service import UsageMetric, enforce_limit, record_usage
from app.modules.notifications.service import create_approval_request
from app.modules.plugins.crypto import CredentialVault
from app.modules.workflows.definition import (
    as_summary_object,
    build_compensation_plan,
    compensation_policy,
    execution_policy,
)
from app.modules.workflows.models import Workflow, WorkflowExecution
from app.modules.workflows.provider import (
    WorkflowProvider,
    WorkflowProviderError,
    WorkflowProviderUnavailable,
    get_workflow_provider,
)
from app.modules.workflows.provider_resilience import (
    ProviderCircuitOpen,
    ensure_provider_available,
    record_provider_failure,
    record_provider_success,
)
from app.modules.workflows.security import sign_webhook_body


def human_approval_configuration(definition: dict[str, Any]) -> dict[str, Any] | None:
    for node in definition.get("nodes", []):
        if isinstance(node, dict) and node.get("type") == "action.human_approval":
            config = node.get("config")
            return dict(config) if isinstance(config, dict) else {}
    return None


async def run_workflow(
    workflow: Workflow,
    input_data: dict[str, Any],
    database: AsyncSession,
    settings: Settings,
    *,
    source: str,
    requested_by_user_id: UUID | None,
    existing_execution: WorkflowExecution | None = None,
    bypass_approval: bool = False,
    provider: WorkflowProvider | None = None,
) -> WorkflowExecution:
    runtime_provider = provider or get_workflow_provider(settings)
    if not runtime_provider.configured:
        raise HTTPException(
            status_code=503,
            detail="Execução de automações indisponível no ambiente remoto reduzido.",
        )
    policy = execution_policy(workflow.definition)
    compensation = compensation_policy(workflow.definition)
    try:
        await ensure_provider_available(
            database, company_id=workflow.company_id, provider=runtime_provider.key
        )
    except ProviderCircuitOpen as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    active_executions = await database.scalar(
        select(func.count(WorkflowExecution.id)).where(
            WorkflowExecution.company_id == workflow.company_id,
            WorkflowExecution.workflow_id == workflow.id,
            WorkflowExecution.status == "running",
        )
    )
    if (active_executions or 0) >= int(policy["concurrency_limit"]):
        raise HTTPException(
            status_code=409,
            detail="A automacao atingiu o limite de execucoes simultaneas.",
        )
    await enforce_limit(
        database,
        company_id=workflow.company_id,
        metric=UsageMetric.WORKFLOW_EXECUTIONS,
        enforcement_enabled=settings.billing_enforcement_enabled,
    )
    approval_config = human_approval_configuration(workflow.definition)
    if approval_config is not None and not bypass_approval:
        execution = existing_execution or WorkflowExecution(
            company_id=workflow.company_id,
            workflow_id=workflow.id,
            requested_by_user_id=requested_by_user_id,
            source=source,
            status="waiting",
            provider_key=runtime_provider.key,
            input_summary=as_summary_object(input_data),
        )
        if existing_execution is None:
            database.add(execution)
        execution.status = "waiting"
        execution.input_summary = as_summary_object(input_data)
        await database.flush()
        encrypted_payload = CredentialVault(settings.encryption_key).encrypt({"input": input_data})
        await create_approval_request(
            database,
            company_id=workflow.company_id,
            requested_by_user_id=requested_by_user_id,
            source_type="workflow",
            title=f"Aprovar execução: {workflow.name}",
            description="A automação foi pausada antes da execução e aguarda uma decisão humana.",
            context={
                "workflow_name": workflow.name,
                "input_summary": execution.input_summary,
                "approver_role": approval_config.get("approver_role", "owner"),
            },
            workflow_id=workflow.id,
            workflow_execution_id=execution.id,
            encrypted_payload=encrypted_payload,
            reminder_minutes=settings.notification_reminder_minutes,
        )
        await database.commit()
        await database.refresh(execution)
        return execution

    execution = existing_execution or WorkflowExecution(
        company_id=workflow.company_id,
        workflow_id=workflow.id,
        requested_by_user_id=requested_by_user_id,
        source=source,
        provider_key=runtime_provider.key,
        input_summary=as_summary_object(input_data),
    )
    if existing_execution is None:
        database.add(execution)
    execution.status = "running"
    execution.started_at = utc_now()
    execution.finished_at = None
    execution.error_summary = None
    await database.flush()
    await database.commit()
    await database.refresh(execution)
    if execution.cancellation_requested_at is not None:
        execution.status = "canceled"
        execution.canceled_at = utc_now()
        if "canceled" in compensation["on_status"] and compensation["enabled"]:
            execution.compensation_plan = build_compensation_plan(workflow.definition)
            execution.compensation_status = "pending"
        await database.commit()
        await database.refresh(execution)
        return execution
    internal_payload = {
        "company_id": str(workflow.company_id),
        "workflow_id": str(workflow.id),
        "execution_id": str(execution.id),
        "input": input_data,
    }
    canonical = json.dumps(
        internal_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    internal_payload["orkestral_signature"] = sign_webhook_body(settings.encryption_key, canonical)
    started = perf_counter()
    try:
        provider_result = await asyncio.wait_for(
            runtime_provider.trigger_workflow(workflow.internal_webhook_path, internal_payload),
            timeout=float(policy["timeout_seconds"]),
        )
        output = provider_result.output
        execution.external_execution_id = provider_result.execution_id
        execution.status = "success"
        execution.output_summary = as_summary_object(output)
        await record_provider_success(
            database, company_id=workflow.company_id, provider=runtime_provider.key
        )
    except WorkflowProviderUnavailable as exc:
        execution.status = "error"
        execution.error_summary = str(exc)
        await record_provider_failure(
            database,
            company_id=workflow.company_id,
            provider=runtime_provider.key,
            error_code=type(exc).__name__,
            threshold=settings.workflow_circuit_failure_threshold,
            reset_seconds=settings.workflow_circuit_reset_seconds,
        )
    except WorkflowProviderError as exc:
        execution.status = "error"
        execution.error_summary = str(exc)
    except TimeoutError:
        execution.status = "error"
        execution.error_summary = "A automacao excedeu o tempo limite configurado."
        await record_provider_failure(
            database,
            company_id=workflow.company_id,
            provider=runtime_provider.key,
            error_code="workflow_timeout",
            threshold=settings.workflow_circuit_failure_threshold,
            reset_seconds=settings.workflow_circuit_reset_seconds,
        )
    await database.refresh(
        execution,
        attribute_names=["cancellation_requested_at", "canceled_by_user_id", "cancel_reason"],
    )
    if execution.cancellation_requested_at is not None:
        execution.status = "canceled"
        execution.canceled_at = utc_now()
        execution.output_summary = {}
    if execution.status in compensation["on_status"] and compensation["enabled"]:
        execution.compensation_plan = build_compensation_plan(workflow.definition)
        execution.compensation_status = "pending"
    else:
        execution.compensation_plan = []
        execution.compensation_status = "not_required"
    execution.duration_ms = max(0, round((perf_counter() - started) * 1_000))
    execution.finished_at = utc_now()
    await record_usage(
        database,
        company_id=workflow.company_id,
        metric=UsageMetric.WORKFLOW_EXECUTIONS,
        quantity=1,
        metadata={
            "workflow_id": str(workflow.id),
            "execution_id": str(execution.id),
            "source": source,
            "status": execution.status,
        },
        idempotency_key=f"workflow-execution:{execution.id}",
    )
    await database.commit()
    await database.refresh(execution)
    return execution
