from __future__ import annotations

import json
from time import perf_counter
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select

from app.core.config import Settings
from app.core.dependencies import DatabaseSession, RedisClient, RequestSettings
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.plugins.crypto import CredentialVault, CredentialVaultError
from app.modules.workflows.definition import (
    WorkflowDefinitionError,
    as_summary_object,
    export_definition,
    prepare_definition,
)
from app.modules.workflows.models import Workflow, WorkflowExecution
from app.modules.workflows.schemas import (
    WorkflowCreate,
    WorkflowCreatedResponse,
    WorkflowEngineStatusResponse,
    WorkflowExecuteRequest,
    WorkflowExecutionResponse,
    WorkflowExportResponse,
    WorkflowResponse,
    WorkflowUpdate,
    WorkflowWebhookSecretResponse,
)
from app.modules.workflows.security import (
    new_internal_webhook_path,
    new_webhook_key,
    new_webhook_secret,
    sign_webhook_body,
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


async def _get_workflow(
    database: DatabaseSession, company_id: UUID, workflow_id: UUID
) -> Workflow:
    workflow = await database.scalar(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.company_id == company_id,
        )
    )
    if workflow is None:
        raise HTTPException(status_code=404, detail="Automação não encontrada.")
    return workflow


async def _sync_workflow(workflow: Workflow, settings: Settings) -> None:
    client = N8nClient(settings)
    try:
        if workflow.n8n_workflow_id:
            result = await client.update_workflow(
                workflow.n8n_workflow_id, workflow.name, workflow.definition
            )
        else:
            result = await client.create_workflow(workflow.name, workflow.definition)
            workflow.n8n_workflow_id = str(result.get("id") or "") or None
        workflow.n8n_version_id = str(result.get("versionId") or "") or None
        workflow.sync_status = "synced"
        workflow.last_error = None
    except N8nClientError as exc:
        workflow.sync_status = "error"
        workflow.last_error = str(exc)


async def _create_workflow_record(
    payload: WorkflowCreate,
    principal: Principal,
    database: DatabaseSession,
    settings: Settings,
) -> tuple[Workflow, str]:
    context = get_request_context(principal)
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
    await _sync_workflow(workflow, settings)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="workflow.created",
        target_type="workflow",
        target_id=workflow.id,
        details={"sync_status": workflow.sync_status},
    )
    await database.commit()
    await database.refresh(workflow)
    return workflow, secret


async def _run_workflow(
    workflow: Workflow,
    input_data: dict[str, Any],
    database: DatabaseSession,
    settings: Settings,
    *,
    source: str,
    requested_by_user_id: UUID | None,
) -> WorkflowExecution:
    execution = WorkflowExecution(
        company_id=workflow.company_id,
        workflow_id=workflow.id,
        requested_by_user_id=requested_by_user_id,
        source=source,
        status="running",
        input_summary=as_summary_object(input_data),
        started_at=utc_now(),
    )
    database.add(execution)
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
    internal_payload["orkestral_signature"] = sign_webhook_body(
        settings.encryption_key, canonical
    )
    started = perf_counter()
    try:
        output = await N8nClient(settings).trigger_webhook(
            workflow.internal_webhook_path, internal_payload
        )
        execution.status = "success"
        execution.output_summary = as_summary_object(output)
    except N8nClientError as exc:
        execution.status = "error"
        execution.error_summary = str(exc)
    execution.duration_ms = max(0, round((perf_counter() - started) * 1_000))
    execution.finished_at = utc_now()
    await database.commit()
    await database.refresh(execution)
    return execution


@router.get("/engine/status", response_model=WorkflowEngineStatusResponse)
async def engine_status(
    principal: CanViewWorkflows, settings: RequestSettings
) -> WorkflowEngineStatusResponse:
    del principal
    client = N8nClient(settings)
    if not client.configured:
        return WorkflowEngineStatusResponse(
            configured=False,
            available=False,
            message="O motor interno aguarda configuração administrativa.",
        )
    try:
        await client.test_connection()
    except N8nClientError as exc:
        return WorkflowEngineStatusResponse(
            configured=True, available=False, message=str(exc)
        )
    return WorkflowEngineStatusResponse(
        configured=True,
        available=True,
        message="Motor de automação conectado e disponível.",
    )


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
    workflow, secret = await _create_workflow_record(
        payload, principal, database, settings
    )
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
    workflow, secret = await _create_workflow_record(
        payload, principal, database, settings
    )
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
    return _workflow_response(
        await _get_workflow(database, context.company_id, workflow_id)
    )


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
    workflow.updated_at = utc_now()
    await _sync_workflow(workflow, settings)
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


@router.post("/{workflow_id}/sync", response_model=WorkflowResponse)
async def sync_workflow(
    workflow_id: UUID,
    principal: CanConfigureWorkflows,
    database: DatabaseSession,
    settings: RequestSettings,
) -> WorkflowResponse:
    context = get_request_context(principal)
    workflow = await _get_workflow(database, context.company_id, workflow_id)
    await _sync_workflow(workflow, settings)
    await database.commit()
    await database.refresh(workflow)
    return _workflow_response(workflow)


@router.post("/{workflow_id}/activate", response_model=WorkflowResponse)
async def activate_workflow(
    workflow_id: UUID,
    principal: CanConfigureWorkflows,
    database: DatabaseSession,
    settings: RequestSettings,
) -> WorkflowResponse:
    context = get_request_context(principal)
    workflow = await _get_workflow(database, context.company_id, workflow_id)
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
    execution = await _run_workflow(
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
        action="workflow.executed",
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


@router.post("/{workflow_id}/duplicate", response_model=WorkflowCreatedResponse, status_code=status.HTTP_201_CREATED)
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
    workflow, secret = await _create_workflow_record(
        payload, principal, database, settings
    )
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
        raise HTTPException(status_code=503, detail="Webhook temporariamente indisponível.") from exc
    if not verify_webhook_signature(
        secret, body, request.headers.get("X-Orkestral-Signature")
    ):
        raise HTTPException(status_code=401, detail="Assinatura do webhook inválida.")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="O webhook deve enviar JSON válido.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="O webhook deve enviar um objeto JSON.")
    execution = await _run_workflow(
        workflow,
        payload,
        database,
        settings,
        source="webhook",
        requested_by_user_id=None,
    )
    return _execution_response(execution)
