from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.dependencies import DatabaseSession, RedisClient, RequestSettings
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.billing.service import UsageMetric, enforce_limit, record_usage
from app.modules.events.models import EventContract, EventDelivery, EventSubscription
from app.modules.events.operations_service import validate_payload
from app.modules.notifications.models import ApprovalRequest
from app.modules.plugins.crypto import CredentialVault, CredentialVaultError
from app.modules.workflows.compiler import (
    analyze_compiler_compatibility,
    compile_definition,
    compiler_compatibility,
)
from app.modules.workflows.definition import (
    WorkflowDefinitionError,
    analyze_definition,
    block_catalog,
    compare_definitions,
    compensation_policy,
    export_definition,
    prepare_definition,
)
from app.modules.workflows.execution import run_workflow
from app.modules.workflows.models import Workflow, WorkflowExecution, WorkflowVersion
from app.modules.workflows.provider_resilience import provider_circuit_snapshot
from app.modules.workflows.schemas import (
    WorkflowComparisonResponse,
    WorkflowCancelRequest,
    WorkflowCreate,
    WorkflowCreatedResponse,
    WorkflowDefinitionRequest,
    WorkflowEngineStatusResponse,
    WorkflowExecuteRequest,
    WorkflowExecutionResponse,
    WorkflowExportResponse,
    WorkflowResponse,
    WorkflowMetricsResponse,
    WorkflowSimulationRequest,
    WorkflowSimulationResponse,
    WorkflowUpdate,
    WorkflowValidationResponse,
    WorkflowVersionResponse,
    WorkflowWebhookSecretResponse,
)
from app.modules.workflows.simulation import simulate_definition
from app.modules.workflows.security import (
    new_internal_webhook_path,
    new_webhook_key,
    new_webhook_secret,
    verify_webhook_signature,
)
from app.modules.workflows.services.n8n_client import N8nClient, N8nClientError

router = APIRouter(prefix="/workflows", tags=["workflows"])
webhook_router = APIRouter(prefix="/webhooks/workflows", tags=["workflow-webhooks"])
CanViewWorkflows = Annotated[Principal, Depends(require_permission("workflows.view"))]
CanExecuteWorkflows = Annotated[Principal, Depends(require_permission("workflows.execute"))]
CanConfigureWorkflows = Annotated[Principal, Depends(require_permission("workflows.configure"))]


def _workflow_response(workflow: Workflow) -> WorkflowResponse:
    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        definition=workflow.definition,
        version=workflow.version,
        status=workflow.status,
        sync_status=workflow.sync_status,
        webhook_url=f"/api/webhooks/workflows/{workflow.public_webhook_key}",
        last_error=workflow.last_error,
        published_at=workflow.published_at,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
    )


def _execution_response(execution: WorkflowExecution) -> WorkflowExecutionResponse:
    return WorkflowExecutionResponse.model_validate(execution, from_attributes=True)


def _version_record(
    workflow: Workflow,
    user_id: UUID | None,
    change_summary: str | None,
) -> WorkflowVersion:
    return WorkflowVersion(
        company_id=workflow.company_id,
        workflow_id=workflow.id,
        created_by_user_id=user_id,
        version=workflow.version,
        name=workflow.name,
        description=workflow.description,
        definition=workflow.definition,
        change_summary=change_summary,
    )


def _assert_publishable(definition: dict[str, Any]) -> None:
    issues = [*analyze_definition(definition), *analyze_compiler_compatibility(definition)]
    errors = [issue for issue in issues if issue["severity"] == "error"]
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Corrija a definicao antes de publicar.", "issues": errors},
        )


async def _get_workflow(database: DatabaseSession, company_id: UUID, workflow_id: UUID) -> Workflow:
    workflow = await database.scalar(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.company_id == company_id,
        )
    )
    if workflow is None:
        raise HTTPException(status_code=404, detail="Automação não encontrada.")
    return workflow


def _domain_event_bindings(definition: dict[str, Any]) -> dict[str, tuple[int, int]]:
    bindings: dict[str, tuple[int, int]] = {}
    for node in definition.get("nodes", []):
        if not isinstance(node, dict) or node.get("type") != "trigger.domain_event":
            continue
        config = node.get("config", {})
        if not isinstance(config, dict):
            continue
        event_type = str(config.get("event_type", ""))
        bindings[event_type] = (
            int(config.get("event_version", 1)),
            int(config.get("max_attempts", 8)),
        )
    return bindings


async def _assert_domain_event_contracts(database: DatabaseSession, workflow: Workflow) -> None:
    for event_type, (version, _) in _domain_event_bindings(workflow.definition).items():
        contract = await database.scalar(
            select(EventContract.id).where(
                EventContract.company_id == workflow.company_id,
                EventContract.event_type == event_type,
                EventContract.version == version,
                EventContract.status == "published",
            )
        )
        if contract is None:
            raise HTTPException(
                status_code=422,
                detail=f"Publique o contrato {event_type} v{version} antes da automacao.",
            )


async def _sync_domain_event_subscriptions(
    database: DatabaseSession, workflow: Workflow, user_id: UUID
) -> None:
    bindings = _domain_event_bindings(workflow.definition)
    rows = list(
        await database.scalars(
            select(EventSubscription).where(
                EventSubscription.company_id == workflow.company_id,
                EventSubscription.workflow_id == workflow.id,
                EventSubscription.delivery_mode == "workflow",
            )
        )
    )
    by_type = {item.event_type: item for item in rows}
    for subscription in rows:
        binding = bindings.get(subscription.event_type)
        if binding is None:
            subscription.active = False
            continue
        version, max_attempts = binding
        subscription.min_version = version
        subscription.max_version = version
        subscription.max_attempts = max_attempts
        subscription.active = True
    for event_type, (version, max_attempts) in bindings.items():
        if event_type in by_type:
            continue
        database.add(
            EventSubscription(
                company_id=workflow.company_id,
                name=f"Automacao: {workflow.name}"[:120],
                consumer_name=f"workflow.{workflow.id}",
                event_type=event_type,
                min_version=version,
                max_version=version,
                delivery_mode="workflow",
                workflow_id=workflow.id,
                active=True,
                max_attempts=max_attempts,
                created_by_user_id=user_id,
            )
        )


async def _deactivate_domain_event_subscriptions(
    database: DatabaseSession, workflow: Workflow
) -> None:
    rows = await database.scalars(
        select(EventSubscription).where(
            EventSubscription.company_id == workflow.company_id,
            EventSubscription.workflow_id == workflow.id,
        )
    )
    for subscription in rows:
        subscription.active = False


async def _sync_workflow(workflow: Workflow, settings: Settings) -> None:
    if not settings.n8n_enabled:
        workflow.sync_status = "error"
        workflow.last_error = "n8n indisponível no ambiente remoto reduzido."
        return
    client = N8nClient(settings)
    try:
        compiled = compile_definition(
            workflow.definition,
            internal_webhook_path=workflow.internal_webhook_path,
        )
        if workflow.n8n_workflow_id:
            result = await client.update_workflow_with_rollback(
                workflow.n8n_workflow_id, workflow.name, compiled
            )
        else:
            result = await client.create_workflow(workflow.name, compiled)
            workflow.n8n_workflow_id = str(result.get("id") or "") or None
        workflow.n8n_version_id = str(result.get("versionId") or "") or None
        workflow.sync_status = "synced"
        workflow.last_error = None
    except (N8nClientError, WorkflowDefinitionError) as exc:
        workflow.sync_status = "error"
        workflow.last_error = str(exc)


async def _create_workflow_record(
    payload: WorkflowCreate,
    principal: Principal,
    database: DatabaseSession,
    settings: Settings,
) -> tuple[Workflow, str]:
    context = get_request_context(principal)
    await enforce_limit(
        database,
        company_id=context.company_id,
        metric=UsageMetric.WORKFLOWS,
        enforcement_enabled=settings.billing_enforcement_enabled,
    )
    internal_path = new_internal_webhook_path()
    secret = new_webhook_secret()
    try:
        definition = prepare_definition(payload.definition, internal_path)
    except WorkflowDefinitionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    workflow = Workflow(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        name=payload.name,
        description=payload.description,
        definition=definition,
        internal_webhook_path=internal_path,
        public_webhook_key=new_webhook_key(),
        encrypted_webhook_secret=CredentialVault(settings.encryption_key).encrypt(
            {"secret": secret}
        ),
    )
    database.add(workflow)
    await database.flush()
    database.add(_version_record(workflow, context.user_id, "Versao inicial"))
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="workflow.created",
        target_type="workflow",
        target_id=workflow.id,
        details={"sync_status": workflow.sync_status},
    )
    await record_usage(
        database,
        company_id=context.company_id,
        metric=UsageMetric.WORKFLOWS,
        quantity=1,
        metadata={"workflow_id": str(workflow.id)},
        idempotency_key=f"workflow:{workflow.id}",
    )
    await database.commit()
    await database.refresh(workflow)
    return workflow, secret


@router.get("/engine/status", response_model=WorkflowEngineStatusResponse)
async def engine_status(
    principal: CanViewWorkflows,
    database: DatabaseSession,
    settings: RequestSettings,
) -> WorkflowEngineStatusResponse:
    context = get_request_context(principal)
    circuit = await provider_circuit_snapshot(
        database, company_id=context.company_id, provider="n8n"
    )
    circuit_fields = {
        "circuit_state": circuit["state"],
        "circuit_failures": circuit["failure_count"],
        "circuit_retry_at": circuit["retry_at"],
    }
    if not settings.n8n_enabled:
        return WorkflowEngineStatusResponse(
            configured=False,
            available=False,
            message="n8n indisponível no ambiente remoto reduzido.",
            **circuit_fields,
        )
    client = N8nClient(settings)
    if not client.configured:
        return WorkflowEngineStatusResponse(
            configured=False,
            available=False,
            message="O motor interno aguarda configuração administrativa.",
            **circuit_fields,
        )
    try:
        await client.test_connection()
    except N8nClientError as exc:
        return WorkflowEngineStatusResponse(
            configured=True, available=False, message=str(exc), **circuit_fields
        )
    return WorkflowEngineStatusResponse(
        configured=True,
        available=True,
        message="Motor de automação conectado e disponível.",
        **circuit_fields,
    )


@router.get("/blocks/catalog", response_model=list[dict[str, Any]])
async def list_workflow_blocks(principal: CanViewWorkflows) -> list[dict[str, Any]]:
    del principal
    return block_catalog()


@router.get("/blocks/compatibility", response_model=list[dict[str, Any]])
async def list_workflow_block_compatibility(
    principal: CanViewWorkflows,
) -> list[dict[str, Any]]:
    del principal
    return compiler_compatibility()


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    principal: CanViewWorkflows, database: DatabaseSession
) -> list[WorkflowResponse]:
    context = get_request_context(principal)
    workflows = list(
        await database.scalars(
            select(Workflow)
            .where(Workflow.company_id == context.company_id)
            .order_by(Workflow.updated_at.desc())
        )
    )
    return [_workflow_response(workflow) for workflow in workflows]


@router.post("", response_model=WorkflowCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    payload: WorkflowCreate,
    principal: CanConfigureWorkflows,
    database: DatabaseSession,
    settings: RequestSettings,
) -> WorkflowCreatedResponse:
    workflow, secret = await _create_workflow_record(payload, principal, database, settings)
    return WorkflowCreatedResponse(
        **_workflow_response(workflow).model_dump(), webhook_secret=secret
    )


@router.post("/import", response_model=WorkflowCreatedResponse, status_code=status.HTTP_201_CREATED)
async def import_workflow(
    payload: WorkflowCreate,
    principal: CanConfigureWorkflows,
    database: DatabaseSession,
    settings: RequestSettings,
) -> WorkflowCreatedResponse:
    workflow, secret = await _create_workflow_record(payload, principal, database, settings)
    return WorkflowCreatedResponse(
        **_workflow_response(workflow).model_dump(), webhook_secret=secret
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    principal: CanViewWorkflows,
    database: DatabaseSession,
) -> WorkflowResponse:
    context = get_request_context(principal)
    return _workflow_response(await _get_workflow(database, context.company_id, workflow_id))


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    payload: WorkflowUpdate,
    principal: CanConfigureWorkflows,
    database: DatabaseSession,
    settings: RequestSettings,
) -> WorkflowResponse:
    context = get_request_context(principal)
    workflow = await _get_workflow(database, context.company_id, workflow_id)
    if payload.name is not None:
        workflow.name = payload.name.strip()
    if "description" in payload.model_fields_set:
        workflow.description = payload.description
    if payload.definition is not None:
        try:
            workflow.definition = prepare_definition(
                payload.definition, workflow.internal_webhook_path
            )
        except WorkflowDefinitionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    workflow.version += 1
    workflow.status = "draft"
    workflow.sync_status = "pending"
    workflow.last_error = None
    workflow.updated_at = utc_now()
    database.add(
        _version_record(
            workflow,
            context.user_id,
            payload.change_summary or "Rascunho atualizado",
        )
    )
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="workflow.updated",
        target_type="workflow",
        target_id=workflow.id,
        details={"version": workflow.version, "sync_status": workflow.sync_status},
    )
    await database.commit()
    await database.refresh(workflow)
    return _workflow_response(workflow)


@router.post("/{workflow_id}/validate", response_model=WorkflowValidationResponse)
async def validate_workflow_draft(
    workflow_id: UUID,
    payload: WorkflowDefinitionRequest,
    principal: CanConfigureWorkflows,
    database: DatabaseSession,
) -> WorkflowValidationResponse:
    context = get_request_context(principal)
    workflow = await _get_workflow(database, context.company_id, workflow_id)
    definition = payload.definition if payload.definition is not None else workflow.definition
    issues = [*analyze_definition(definition), *analyze_compiler_compatibility(definition)]
    return WorkflowValidationResponse(
        valid=not any(issue["severity"] == "error" for issue in issues),
        issues=issues,
    )


@router.post("/{workflow_id}/simulate", response_model=WorkflowSimulationResponse)
async def simulate_workflow_draft(
    workflow_id: UUID,
    payload: WorkflowSimulationRequest,
    principal: CanConfigureWorkflows,
    database: DatabaseSession,
) -> WorkflowSimulationResponse:
    context = get_request_context(principal)
    workflow = await _get_workflow(database, context.company_id, workflow_id)
    definition = payload.definition if payload.definition is not None else workflow.definition
    result = simulate_definition(definition, payload.input)
    result["issues"].extend(analyze_compiler_compatibility(definition))
    event_wrapper = payload.input.get("event")
    event_payload = (
        event_wrapper.get("payload", {}) if isinstance(event_wrapper, dict) else payload.input
    )
    if not isinstance(event_payload, dict):
        event_payload = {}
    for event_type, (version, _) in _domain_event_bindings(definition).items():
        contract = await database.scalar(
            select(EventContract).where(
                EventContract.company_id == context.company_id,
                EventContract.event_type == event_type,
                EventContract.version == version,
                EventContract.status == "published",
            )
        )
        if contract is None:
            result["issues"].append(
                {
                    "severity": "error",
                    "code": "event_contract_missing",
                    "message": f"Contrato publicado ausente: {event_type} v{version}.",
                    "node_id": None,
                }
            )
            continue
        for message in validate_payload(event_payload, contract.payload_schema):
            result["issues"].append(
                {
                    "severity": "error",
                    "code": "event_payload_invalid",
                    "message": message,
                    "node_id": None,
                }
            )
    result["valid"] = not any(item["severity"] == "error" for item in result["issues"])
    result["publishable"] = result["valid"]
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="workflow.simulated",
        target_type="workflow",
        target_id=workflow.id,
        details={
            "version": workflow.version,
            "estimated_steps": result["estimated_steps"],
            "blocked_side_effects": result["blocked_side_effects"],
            "valid": result["valid"],
        },
    )
    await database.commit()
    return WorkflowSimulationResponse.model_validate(result)


@router.post("/{workflow_id}/sync", response_model=WorkflowResponse)
async def sync_workflow(
    workflow_id: UUID,
    principal: CanConfigureWorkflows,
    database: DatabaseSession,
    settings: RequestSettings,
) -> WorkflowResponse:
    context = get_request_context(principal)
    workflow = await _get_workflow(database, context.company_id, workflow_id)
    await _assert_domain_event_contracts(database, workflow)
    _assert_publishable(workflow.definition)
    await _sync_workflow(workflow, settings)
    await database.commit()
    await database.refresh(workflow)
    return _workflow_response(workflow)


@router.post("/{workflow_id}/publish", response_model=WorkflowResponse)
async def publish_workflow(
    workflow_id: UUID,
    principal: CanConfigureWorkflows,
    database: DatabaseSession,
    settings: RequestSettings,
) -> WorkflowResponse:
    return await activate_workflow(workflow_id, principal, database, settings)


@router.post("/{workflow_id}/activate", response_model=WorkflowResponse)
async def activate_workflow(
    workflow_id: UUID,
    principal: CanConfigureWorkflows,
    database: DatabaseSession,
    settings: RequestSettings,
) -> WorkflowResponse:
    context = get_request_context(principal)
    workflow = await _get_workflow(database, context.company_id, workflow_id)
    await _assert_domain_event_contracts(database, workflow)
    if workflow.sync_status != "synced" or not workflow.n8n_workflow_id:
        await _sync_workflow(workflow, settings)
    if workflow.sync_status != "synced" or not workflow.n8n_workflow_id:
        await database.commit()
        raise HTTPException(
            status_code=503,
            detail=workflow.last_error or "A automação ainda não foi sincronizada.",
        )
    try:
        result = await N8nClient(settings).activate_workflow(workflow.n8n_workflow_id)
    except N8nClientError as exc:
        workflow.status = "error"
        workflow.last_error = str(exc)
        await database.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    workflow.status = "active"
    workflow.n8n_version_id = str(result.get("versionId") or workflow.n8n_version_id or "") or None
    workflow.published_at = utc_now()
    workflow.last_error = None
    await _sync_domain_event_subscriptions(database, workflow, context.user_id)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="workflow.activated",
        target_type="workflow",
        target_id=workflow.id,
        details={"version": workflow.version},
    )
    await database.commit()
    await database.refresh(workflow)
    return _workflow_response(workflow)


@router.post("/{workflow_id}/deactivate", response_model=WorkflowResponse)
async def deactivate_workflow(
    workflow_id: UUID,
    principal: CanConfigureWorkflows,
    database: DatabaseSession,
    settings: RequestSettings,
) -> WorkflowResponse:
    context = get_request_context(principal)
    workflow = await _get_workflow(database, context.company_id, workflow_id)
    if workflow.n8n_workflow_id:
        try:
            await N8nClient(settings).deactivate_workflow(workflow.n8n_workflow_id)
        except N8nClientError as exc:
            workflow.last_error = str(exc)
            await database.commit()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    workflow.status = "inactive"
    workflow.last_error = None
    await _deactivate_domain_event_subscriptions(database, workflow)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="workflow.deactivated",
        target_type="workflow",
        target_id=workflow.id,
        details={},
    )
    await database.commit()
    await database.refresh(workflow)
    return _workflow_response(workflow)


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow(
    workflow_id: UUID,
    payload: WorkflowExecuteRequest,
    principal: CanExecuteWorkflows,
    database: DatabaseSession,
    settings: RequestSettings,
) -> WorkflowExecutionResponse:
    context = get_request_context(principal)
    workflow = await _get_workflow(database, context.company_id, workflow_id)
    if workflow.status != "active":
        raise HTTPException(status_code=409, detail="Ative a automação antes de executá-la.")
    execution = await run_workflow(
        workflow,
        payload.input,
        database,
        settings,
        source="manual",
        requested_by_user_id=context.user_id,
    )
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="workflow.approval_requested"
        if execution.status == "waiting"
        else "workflow.executed",
        target_type="workflow_execution",
        target_id=execution.id,
        details={"workflow_id": str(workflow.id), "status": execution.status},
    )
    await database.commit()
    return _execution_response(execution)


@router.get("/{workflow_id}/executions", response_model=list[WorkflowExecutionResponse])
async def list_workflow_executions(
    workflow_id: UUID,
    principal: CanViewWorkflows,
    database: DatabaseSession,
) -> list[WorkflowExecutionResponse]:
    context = get_request_context(principal)
    await _get_workflow(database, context.company_id, workflow_id)
    executions = list(
        await database.scalars(
            select(WorkflowExecution)
            .where(
                WorkflowExecution.company_id == context.company_id,
                WorkflowExecution.workflow_id == workflow_id,
            )
            .order_by(WorkflowExecution.created_at.desc())
            .limit(100)
        )
    )
    return [_execution_response(execution) for execution in executions]


@router.post(
    "/{workflow_id}/executions/{execution_id}/cancel",
    response_model=WorkflowExecutionResponse,
)
async def cancel_workflow_execution(
    workflow_id: UUID,
    execution_id: UUID,
    payload: WorkflowCancelRequest,
    principal: CanExecuteWorkflows,
    database: DatabaseSession,
    settings: RequestSettings,
) -> WorkflowExecutionResponse:
    context = get_request_context(principal)
    workflow = await _get_workflow(database, context.company_id, workflow_id)
    execution = await database.scalar(
        select(WorkflowExecution).where(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.workflow_id == workflow_id,
            WorkflowExecution.company_id == context.company_id,
        )
    )
    if execution is None:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada.")
    if execution.status in {"success", "error", "canceled"}:
        raise HTTPException(status_code=409, detail="A execucao ja foi finalizada.")
    now = utc_now()
    execution.cancellation_requested_at = now
    execution.canceled_by_user_id = context.user_id
    execution.cancel_reason = payload.reason.strip() if payload.reason else None
    if execution.status == "running":
        client = N8nClient(settings)
        if execution.external_execution_id and client.supports_remote_cancellation:
            try:
                requested = await client.cancel_execution(execution.external_execution_id)
                execution.remote_cancel_status = "requested" if requested else "unsupported"
            except N8nClientError:
                execution.remote_cancel_status = "failed"
        else:
            execution.remote_cancel_status = "unsupported"
    if execution.status in {"queued", "waiting"}:
        execution.status = "canceled"
        execution.canceled_at = now
        execution.finished_at = now
        policy = compensation_policy(workflow.definition)
        if policy["enabled"] and "canceled" in policy["on_status"]:
            execution.compensation_status = "pending"
    approval = await database.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.company_id == context.company_id,
            ApprovalRequest.workflow_execution_id == execution.id,
            ApprovalRequest.status == "pending",
        )
    )
    if approval is not None:
        approval.status = "cancelled"
        approval.decided_at = now
        approval.encrypted_payload = None
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="workflow.execution.cancellation_requested",
        target_type="workflow_execution",
        target_id=execution.id,
        details={
            "workflow_id": str(workflow_id),
            "immediate": execution.status == "canceled",
        },
    )
    await database.commit()
    await database.refresh(execution)
    return _execution_response(execution)


@router.post(
    "/{workflow_id}/executions/{execution_id}/compensation/acknowledge",
    response_model=WorkflowExecutionResponse,
)
async def acknowledge_workflow_compensation(
    workflow_id: UUID,
    execution_id: UUID,
    principal: CanExecuteWorkflows,
    database: DatabaseSession,
) -> WorkflowExecutionResponse:
    context = get_request_context(principal)
    await _get_workflow(database, context.company_id, workflow_id)
    execution = await database.scalar(
        select(WorkflowExecution).where(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.workflow_id == workflow_id,
            WorkflowExecution.company_id == context.company_id,
        )
    )
    if execution is None:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada.")
    if execution.compensation_status != "pending":
        raise HTTPException(status_code=409, detail="Nao existe compensacao pendente.")
    execution.compensation_status = "acknowledged"
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="workflow.compensation.acknowledged",
        target_type="workflow_execution",
        target_id=execution.id,
        details={"workflow_id": str(workflow_id)},
    )
    await database.commit()
    await database.refresh(execution)
    return _execution_response(execution)


@router.get("/{workflow_id}/metrics", response_model=WorkflowMetricsResponse)
async def workflow_metrics(
    workflow_id: UUID,
    principal: CanViewWorkflows,
    database: DatabaseSession,
) -> WorkflowMetricsResponse:
    context = get_request_context(principal)
    await _get_workflow(database, context.company_id, workflow_id)
    base = (
        WorkflowExecution.company_id == context.company_id,
        WorkflowExecution.workflow_id == workflow_id,
    )
    total = int(await database.scalar(select(func.count(WorkflowExecution.id)).where(*base)) or 0)

    async def count_status(status_value: str) -> int:
        return int(
            await database.scalar(
                select(func.count(WorkflowExecution.id)).where(
                    *base, WorkflowExecution.status == status_value
                )
            )
            or 0
        )

    success = await count_status("success")
    errors = await count_status("error")
    canceled = await count_status("canceled")
    waiting = await count_status("waiting")
    running = await count_status("running")
    domain_event_executions = int(
        await database.scalar(
            select(func.count(WorkflowExecution.id)).where(
                *base, WorkflowExecution.source == "domain_event"
            )
        )
        or 0
    )
    cancellation_requests = int(
        await database.scalar(
            select(func.count(WorkflowExecution.id)).where(
                *base, WorkflowExecution.cancellation_requested_at.is_not(None)
            )
        )
        or 0
    )
    compensation_pending = int(
        await database.scalar(
            select(func.count(WorkflowExecution.id)).where(
                *base, WorkflowExecution.compensation_status == "pending"
            )
        )
        or 0
    )
    average_duration = await database.scalar(
        select(func.avg(WorkflowExecution.duration_ms)).where(
            *base, WorkflowExecution.duration_ms.is_not(None)
        )
    )
    replay_count = int(
        await database.scalar(
            select(func.coalesce(func.sum(EventDelivery.replay_count), 0))
            .join(
                EventSubscription,
                EventSubscription.id == EventDelivery.subscription_id,
            )
            .where(
                EventDelivery.company_id == context.company_id,
                EventSubscription.workflow_id == workflow_id,
            )
        )
        or 0
    )
    return WorkflowMetricsResponse(
        total=total,
        success=success,
        errors=errors,
        canceled=canceled,
        waiting=waiting,
        running=running,
        domain_event_executions=domain_event_executions,
        cancellation_requests=cancellation_requests,
        compensation_pending=compensation_pending,
        replay_count=replay_count,
        success_rate=round((success / total * 100) if total else 0.0, 2),
        average_duration_ms=round(float(average_duration or 0), 2),
    )


@router.get("/{workflow_id}/versions", response_model=list[WorkflowVersionResponse])
async def list_workflow_versions(
    workflow_id: UUID,
    principal: CanViewWorkflows,
    database: DatabaseSession,
) -> list[WorkflowVersionResponse]:
    context = get_request_context(principal)
    await _get_workflow(database, context.company_id, workflow_id)
    versions = list(
        await database.scalars(
            select(WorkflowVersion)
            .where(
                WorkflowVersion.company_id == context.company_id,
                WorkflowVersion.workflow_id == workflow_id,
            )
            .order_by(WorkflowVersion.version.desc())
        )
    )
    return [WorkflowVersionResponse.model_validate(item, from_attributes=True) for item in versions]


@router.get("/{workflow_id}/versions/compare", response_model=WorkflowComparisonResponse)
async def compare_workflow_versions(
    workflow_id: UUID,
    from_version: int,
    to_version: int,
    principal: CanViewWorkflows,
    database: DatabaseSession,
) -> WorkflowComparisonResponse:
    context = get_request_context(principal)
    await _get_workflow(database, context.company_id, workflow_id)
    rows = list(
        await database.scalars(
            select(WorkflowVersion).where(
                WorkflowVersion.company_id == context.company_id,
                WorkflowVersion.workflow_id == workflow_id,
                WorkflowVersion.version.in_([from_version, to_version]),
            )
        )
    )
    by_version = {row.version: row for row in rows}
    if from_version not in by_version or to_version not in by_version:
        raise HTTPException(status_code=404, detail="Versao nao encontrada.")
    comparison = compare_definitions(
        by_version[from_version].definition,
        by_version[to_version].definition,
    )
    return WorkflowComparisonResponse(
        from_version=from_version,
        to_version=to_version,
        **comparison,
    )


@router.post("/{workflow_id}/versions/{version}/restore", response_model=WorkflowResponse)
async def restore_workflow_version(
    workflow_id: UUID,
    version: int,
    principal: CanConfigureWorkflows,
    database: DatabaseSession,
) -> WorkflowResponse:
    context = get_request_context(principal)
    workflow = await _get_workflow(database, context.company_id, workflow_id)
    snapshot = await database.scalar(
        select(WorkflowVersion).where(
            WorkflowVersion.company_id == context.company_id,
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.version == version,
        )
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Versao nao encontrada.")
    workflow.name = snapshot.name
    workflow.description = snapshot.description
    workflow.definition = prepare_definition(snapshot.definition, workflow.internal_webhook_path)
    workflow.version += 1
    workflow.status = "draft"
    workflow.sync_status = "pending"
    workflow.last_error = None
    workflow.updated_at = utc_now()
    database.add(_version_record(workflow, context.user_id, f"Restaurada da versao {version}"))
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="workflow.version.restored",
        target_type="workflow",
        target_id=workflow.id,
        details={"source_version": version, "new_version": workflow.version},
    )
    await database.commit()
    await database.refresh(workflow)
    return _workflow_response(workflow)


@router.get("/{workflow_id}/export", response_model=WorkflowExportResponse)
async def export_workflow(
    workflow_id: UUID,
    principal: CanViewWorkflows,
    database: DatabaseSession,
) -> WorkflowExportResponse:
    context = get_request_context(principal)
    workflow = await _get_workflow(database, context.company_id, workflow_id)
    return WorkflowExportResponse(
        name=workflow.name,
        description=workflow.description,
        version=workflow.version,
        definition=export_definition(workflow.definition),
    )


@router.post(
    "/{workflow_id}/duplicate",
    response_model=WorkflowCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_workflow(
    workflow_id: UUID,
    principal: CanConfigureWorkflows,
    database: DatabaseSession,
    settings: RequestSettings,
) -> WorkflowCreatedResponse:
    context = get_request_context(principal)
    source = await _get_workflow(database, context.company_id, workflow_id)
    payload = WorkflowCreate(
        name=f"{source.name} (cópia)",
        description=source.description,
        definition=export_definition(source.definition),
    )
    workflow, secret = await _create_workflow_record(payload, principal, database, settings)
    return WorkflowCreatedResponse(
        **_workflow_response(workflow).model_dump(), webhook_secret=secret
    )


@router.post("/{workflow_id}/webhook-secret", response_model=WorkflowWebhookSecretResponse)
async def rotate_webhook_secret(
    workflow_id: UUID,
    principal: CanConfigureWorkflows,
    database: DatabaseSession,
    settings: RequestSettings,
) -> WorkflowWebhookSecretResponse:
    context = get_request_context(principal)
    workflow = await _get_workflow(database, context.company_id, workflow_id)
    secret = new_webhook_secret()
    workflow.encrypted_webhook_secret = CredentialVault(settings.encryption_key).encrypt(
        {"secret": secret}
    )
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="workflow.webhook_secret.rotated",
        target_type="workflow",
        target_id=workflow.id,
        details={},
    )
    await database.commit()
    return WorkflowWebhookSecretResponse(
        webhook_url=f"/api/webhooks/workflows/{workflow.public_webhook_key}",
        webhook_secret=secret,
    )


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: UUID,
    principal: CanConfigureWorkflows,
    database: DatabaseSession,
    settings: RequestSettings,
) -> Response:
    context = get_request_context(principal)
    workflow = await _get_workflow(database, context.company_id, workflow_id)
    if workflow.status == "active" and workflow.n8n_workflow_id:
        try:
            await N8nClient(settings).deactivate_workflow(workflow.n8n_workflow_id)
        except N8nClientError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="workflow.deleted",
        target_type="workflow",
        target_id=workflow.id,
        details={},
    )
    subscriptions = list(
        await database.scalars(
            select(EventSubscription).where(
                EventSubscription.company_id == context.company_id,
                EventSubscription.workflow_id == workflow.id,
            )
        )
    )
    for subscription in subscriptions:
        await database.delete(subscription)
    await database.delete(workflow)
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@webhook_router.post("/{public_key}", response_model=WorkflowExecutionResponse)
async def receive_workflow_webhook(
    public_key: str,
    request: Request,
    database: DatabaseSession,
    redis: RedisClient,
    settings: RequestSettings,
) -> WorkflowExecutionResponse:
    body = await request.body()
    if len(body) > settings.workflow_max_payload_bytes:
        raise HTTPException(status_code=413, detail="O payload excede o limite permitido.")
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"rate:workflow-webhook:{public_key}:{client_ip}"
    count = int(await redis.incr(rate_key))
    if count == 1:
        await redis.expire(rate_key, 60)
    if count > settings.workflow_webhook_rate_limit:
        raise HTTPException(status_code=429, detail="Limite de chamadas excedido.")
    workflow = await database.scalar(
        select(Workflow).where(
            Workflow.public_webhook_key == public_key,
            Workflow.status == "active",
        )
    )
    if workflow is None:
        raise HTTPException(status_code=404, detail="Webhook não encontrado.")
    try:
        secret_data = CredentialVault(settings.encryption_key).decrypt(
            workflow.encrypted_webhook_secret
        )
        secret = str(secret_data["secret"])
    except (CredentialVaultError, KeyError) as exc:
        raise HTTPException(
            status_code=503, detail="Webhook temporariamente indisponível."
        ) from exc
    if not verify_webhook_signature(secret, body, request.headers.get("X-Orkestral-Signature")):
        raise HTTPException(status_code=401, detail="Assinatura do webhook inválida.")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="O webhook deve enviar JSON válido.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="O webhook deve enviar um objeto JSON.")
    execution = await run_workflow(
        workflow,
        payload,
        database,
        settings,
        source="webhook",
        requested_by_user_id=None,
    )
    return _execution_response(execution)
