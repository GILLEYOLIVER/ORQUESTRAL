from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.crm.customer_cdc_schemas import (
    CustomerCdcAcknowledgeRequest,
    CustomerCdcCheckpointResponse,
    CustomerCdcEventPage,
    CustomerCdcRetentionPreviewResponse,
    CustomerCdcRetentionPurgeRequest,
    CustomerCdcRetentionPurgeResponse,
    CustomerCdcSubscriptionCreate,
    CustomerCdcSubscriptionResponse,
    CustomerCdcSummaryResponse,
)
from app.modules.crm.customer_cdc_service import (
    acknowledge_customer_cdc_checkpoint,
    create_customer_cdc_subscription,
    get_customer_cdc_summary,
    list_customer_cdc_subscriptions,
    list_customer_change_events,
    preview_customer_cdc_retention,
    purge_expired_customer_cdc_events,
    set_customer_cdc_subscription_status,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(prefix="/crm/customer-data/cdc", tags=["customer-cdc"])

ActiveCRM = Annotated[Principal, Depends(require_active_module("crm"))]
CustomerDataReader = Annotated[
    Principal,
    Depends(require_permission("crm.contacts.view")),
]
CustomerDataManager = Annotated[
    Principal,
    Depends(require_permission("crm.contacts.update")),
]


@router.get("/summary", response_model=CustomerCdcSummaryResponse)
async def customer_cdc_summary(
    principal: CustomerDataReader,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerCdcSummaryResponse:
    context = get_request_context(principal)
    return await get_customer_cdc_summary(
        database,
        company_id=context.company_id,
    )


@router.get("/events", response_model=CustomerCdcEventPage)
async def customer_cdc_events(
    principal: CustomerDataReader,
    _: ActiveCRM,
    database: DatabaseSession,
    after_sequence: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> CustomerCdcEventPage:
    context = get_request_context(principal)
    return await list_customer_change_events(
        database,
        company_id=context.company_id,
        after_sequence=after_sequence,
        limit=limit,
    )


@router.get(
    "/subscriptions",
    response_model=list[CustomerCdcSubscriptionResponse],
)
async def customer_cdc_subscriptions(
    principal: CustomerDataReader,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[CustomerCdcSubscriptionResponse]:
    context = get_request_context(principal)
    return await list_customer_cdc_subscriptions(
        database,
        company_id=context.company_id,
    )


@router.post(
    "/subscriptions",
    response_model=CustomerCdcSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_cdc_subscription(
    payload: CustomerCdcSubscriptionCreate,
    principal: CustomerDataManager,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerCdcSubscriptionResponse:
    context = get_request_context(principal)
    subscription = await create_customer_cdc_subscription(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        payload=payload,
    )
    await database.commit()
    return subscription


@router.get(
    "/subscriptions/{subscription_id}/events",
    response_model=CustomerCdcEventPage,
)
async def customer_cdc_subscription_events(
    subscription_id: UUID,
    principal: CustomerDataReader,
    _: ActiveCRM,
    database: DatabaseSession,
    after_sequence: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=200),
) -> CustomerCdcEventPage:
    context = get_request_context(principal)
    return await list_customer_change_events(
        database,
        company_id=context.company_id,
        after_sequence=after_sequence,
        limit=limit,
        subscription_id=subscription_id,
    )


@router.post(
    "/subscriptions/{subscription_id}/acknowledge",
    response_model=CustomerCdcCheckpointResponse,
)
async def acknowledge_cdc_subscription(
    subscription_id: UUID,
    payload: CustomerCdcAcknowledgeRequest,
    principal: CustomerDataManager,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerCdcCheckpointResponse:
    context = get_request_context(principal)
    checkpoint = await acknowledge_customer_cdc_checkpoint(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        subscription_id=subscription_id,
        payload=payload,
    )
    await database.commit()
    return checkpoint


@router.post(
    "/subscriptions/{subscription_id}/pause",
    response_model=CustomerCdcSubscriptionResponse,
)
async def pause_cdc_subscription(
    subscription_id: UUID,
    principal: CustomerDataManager,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerCdcSubscriptionResponse:
    context = get_request_context(principal)
    subscription = await set_customer_cdc_subscription_status(
        database,
        company_id=context.company_id,
        subscription_id=subscription_id,
        target_status="paused",
    )
    await database.commit()
    return subscription


@router.post(
    "/subscriptions/{subscription_id}/resume",
    response_model=CustomerCdcSubscriptionResponse,
)
async def resume_cdc_subscription(
    subscription_id: UUID,
    principal: CustomerDataManager,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerCdcSubscriptionResponse:
    context = get_request_context(principal)
    subscription = await set_customer_cdc_subscription_status(
        database,
        company_id=context.company_id,
        subscription_id=subscription_id,
        target_status="active",
    )
    await database.commit()
    return subscription


@router.get(
    "/retention/preview",
    response_model=CustomerCdcRetentionPreviewResponse,
)
async def customer_cdc_retention_preview(
    principal: CustomerDataReader,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerCdcRetentionPreviewResponse:
    context = get_request_context(principal)
    return await preview_customer_cdc_retention(
        database,
        company_id=context.company_id,
    )


@router.post(
    "/retention/purge",
    response_model=CustomerCdcRetentionPurgeResponse,
)
async def purge_customer_cdc_retention(
    payload: CustomerCdcRetentionPurgeRequest,
    principal: CustomerDataManager,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerCdcRetentionPurgeResponse:
    context = get_request_context(principal)
    response = await purge_expired_customer_cdc_events(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        payload=payload,
    )
    await database.commit()
    return response
