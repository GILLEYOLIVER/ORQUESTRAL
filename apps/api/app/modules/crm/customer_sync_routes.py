from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.crm.customer_sync_schemas import (
    CustomerSyncConnectorCreate,
    CustomerSyncConnectorResponse,
    CustomerSyncExecutionCreate,
    CustomerSyncObservabilityResponse,
    CustomerSyncRunResponse,
)
from app.modules.crm.customer_sync_service import (
    create_sync_connector,
    execute_customer_sync,
    get_sync_observability,
    list_sync_connectors,
    list_sync_runs,
    set_sync_connector_status,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(prefix="/crm/customer-data/sync", tags=["crm-customer-sync"])

ActiveCRM = Annotated[Principal, Depends(require_active_module("crm"))]
CanView = Annotated[Principal, Depends(require_permission("crm.contacts.view"))]
CanManage = Annotated[Principal, Depends(require_permission("crm.contacts.update"))]


def _http_error(exc: LookupError | ValueError) -> HTTPException:
    return HTTPException(
        status_code=404 if isinstance(exc, LookupError) else 409,
        detail=str(exc),
    )


@router.get("/connectors", response_model=list[CustomerSyncConnectorResponse])
async def get_connectors(
    principal: CanView,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[CustomerSyncConnectorResponse]:
    context = get_request_context(principal)
    return await list_sync_connectors(database, company_id=context.company_id)


@router.post(
    "/connectors",
    response_model=CustomerSyncConnectorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_connector(
    payload: CustomerSyncConnectorCreate,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerSyncConnectorResponse:
    context = get_request_context(principal)
    try:
        response = await create_sync_connector(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.post(
    "/connectors/{connector_id}/pause",
    response_model=CustomerSyncConnectorResponse,
)
async def post_pause_connector(
    connector_id: UUID,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerSyncConnectorResponse:
    context = get_request_context(principal)
    try:
        response = await set_sync_connector_status(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            connector_id=connector_id,
            target_status="paused",
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.post(
    "/connectors/{connector_id}/resume",
    response_model=CustomerSyncConnectorResponse,
)
async def post_resume_connector(
    connector_id: UUID,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerSyncConnectorResponse:
    context = get_request_context(principal)
    try:
        response = await set_sync_connector_status(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            connector_id=connector_id,
            target_status="active",
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.post(
    "/connectors/{connector_id}/execute",
    response_model=CustomerSyncRunResponse,
)
async def post_execute_connector(
    connector_id: UUID,
    payload: CustomerSyncExecutionCreate,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerSyncRunResponse:
    context = get_request_context(principal)
    try:
        response = await execute_customer_sync(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            connector_id=connector_id,
            payload=payload,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.get("/runs", response_model=list[CustomerSyncRunResponse])
async def get_runs(
    principal: CanView,
    _: ActiveCRM,
    database: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[CustomerSyncRunResponse]:
    context = get_request_context(principal)
    return await list_sync_runs(database, company_id=context.company_id, limit=limit)


@router.get("/observability", response_model=CustomerSyncObservabilityResponse)
async def get_observability(
    principal: CanView,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerSyncObservabilityResponse:
    context = get_request_context(principal)
    return await get_sync_observability(database, company_id=context.company_id)
