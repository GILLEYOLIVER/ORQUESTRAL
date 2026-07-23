from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.crm.customer_sync_scheduler_schemas import (
    CustomerSyncAdapterHealthResponse,
    CustomerSyncAdapterResponse,
    CustomerSyncCredentialOptionResponse,
    CustomerSyncDispatchResponse,
    CustomerSyncSchedulerSummary,
)
from app.modules.crm.customer_sync_scheduler_service import (
    adapter_catalog,
    list_sync_adapter_health,
    list_sync_credential_options,
    list_sync_dispatches,
    probe_sync_connector_health,
    requeue_sync_dispatch,
    sync_scheduler_summary,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(prefix="/crm/customer-data/sync", tags=["crm-customer-sync-scheduler"])

ActiveCRM = Annotated[Principal, Depends(require_active_module("crm"))]
CanView = Annotated[Principal, Depends(require_permission("crm.contacts.view"))]
CanManage = Annotated[Principal, Depends(require_permission("crm.contacts.update"))]


@router.get("/adapters", response_model=list[CustomerSyncAdapterResponse])
async def get_adapters(
    _: CanView,
    __: ActiveCRM,
) -> list[CustomerSyncAdapterResponse]:
    return adapter_catalog()


@router.get("/adapter-health", response_model=list[CustomerSyncAdapterHealthResponse])
async def get_adapter_health(
    principal: CanView,
    _: ActiveCRM,
    database: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[CustomerSyncAdapterHealthResponse]:
    context = get_request_context(principal)
    return await list_sync_adapter_health(
        database,
        company_id=context.company_id,
        limit=limit,
    )


@router.post(
    "/connectors/{connector_id}/health",
    response_model=CustomerSyncAdapterHealthResponse,
)
async def post_connector_health(
    connector_id: UUID,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerSyncAdapterHealthResponse:
    context = get_request_context(principal)
    try:
        response = await probe_sync_connector_health(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            connector_id=connector_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await database.commit()
    return response


@router.get("/dispatches", response_model=list[CustomerSyncDispatchResponse])
async def get_dispatches(
    principal: CanView,
    _: ActiveCRM,
    database: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[CustomerSyncDispatchResponse]:
    context = get_request_context(principal)
    return await list_sync_dispatches(
        database,
        company_id=context.company_id,
        limit=limit,
    )


@router.get(
    "/credential-options",
    response_model=list[CustomerSyncCredentialOptionResponse],
)
async def get_credential_options(
    principal: CanView,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[CustomerSyncCredentialOptionResponse]:
    context = get_request_context(principal)
    return await list_sync_credential_options(
        database,
        company_id=context.company_id,
    )


@router.post(
    "/dispatches/{dispatch_id}/retry",
    response_model=CustomerSyncDispatchResponse,
)
async def post_dispatch_retry(
    dispatch_id: UUID,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerSyncDispatchResponse:
    context = get_request_context(principal)
    try:
        response = await requeue_sync_dispatch(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            dispatch_id=dispatch_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await database.commit()
    return response


@router.get("/scheduler-summary", response_model=CustomerSyncSchedulerSummary)
async def get_scheduler_summary(
    principal: CanView,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerSyncSchedulerSummary:
    context = get_request_context(principal)
    return await sync_scheduler_summary(database, company_id=context.company_id)
