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
from app.modules.workflows.definition import as_summary_object, execution_policy
from app.modules.workflows.models import Workflow, WorkflowExecution
from app.modules.workflows.security import sign_webhook_body
from app.modules.workflows.services.n8n_client import N8nClient, N8nClientError


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
) -> WorkflowExecution:
    if not settings.n8n_enabled:
        raise HTTPException(
            status_code=503,
            detail="Execução de automações indisponível no ambiente remoto reduzido.",
        )
    policy = execution_policy(workflow.definition)
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
        input_summary=as_summary_object(input_data),
    )
    if existing_execution is None:
        database.add(execution)
    execution.status = "running"
    execution.started_at = utc_now()
    execution.finished_at = None
    execution.error_summary = None
    await database.flush()
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
        output = await asyncio.wait_for(
            N8nClient(settings).trigger_webhook(workflow.internal_webhook_path, internal_payload),
            timeout=float(policy["timeout_seconds"]),
        )
        execution.status = "success"
        execution.output_summary = as_summary_object(output)
    except N8nClientError as exc:
        execution.status = "error"
        execution.error_summary = str(exc)
    except TimeoutError:
        execution.status = "error"
        execution.error_summary = "A automacao excedeu o tempo limite configurado."
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
