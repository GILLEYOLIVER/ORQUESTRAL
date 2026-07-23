from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.crm.customer_segment_schemas import (
    CustomerProfileSearchResponse,
    CustomerSegmentActivationRequest,
    CustomerSegmentActivationResponse,
    CustomerSegmentCreate,
    CustomerSegmentMaterializationResponse,
    CustomerSegmentResponse,
)
from app.modules.crm.customer_segment_service import (
    activate_customer_segment,
    create_customer_segment,
    list_customer_segments,
    materialize_customer_segment,
    publish_customer_segment,
    search_customer_profiles,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(prefix="/crm/customer-data/segments", tags=["customer-segments"])

ActiveCRM = Annotated[Principal, Depends(require_active_module("crm"))]
CanView = Annotated[Principal, Depends(require_permission("crm.segments.view"))]
CanManage = Annotated[Principal, Depends(require_permission("crm.segments.manage"))]
CanActivate = Annotated[Principal, Depends(require_permission("crm.segments.activate"))]


def _http_error(exc: LookupError | ValueError) -> HTTPException:
    return HTTPException(
        status_code=404 if isinstance(exc, LookupError) else 409,
        detail=str(exc),
    )


@router.get("", response_model=list[CustomerSegmentResponse])
async def customer_segments(
    principal: CanView,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[CustomerSegmentResponse]:
    context = get_request_context(principal)
    return await list_customer_segments(database, company_id=context.company_id)


@router.post(
    "",
    response_model=CustomerSegmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_segment(
    payload: CustomerSegmentCreate,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerSegmentResponse:
    context = get_request_context(principal)
    try:
        response = await create_customer_segment(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.post(
    "/{segment_id}/materialize",
    response_model=CustomerSegmentMaterializationResponse,
)
async def materialize_segment(
    segment_id: UUID,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerSegmentMaterializationResponse:
    context = get_request_context(principal)
    try:
        response = await materialize_customer_segment(
            database,
            company_id=context.company_id,
            segment_id=segment_id,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.post(
    "/{segment_id}/publish",
    response_model=CustomerSegmentResponse,
)
async def publish_segment(
    segment_id: UUID,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerSegmentResponse:
    context = get_request_context(principal)
    try:
        response = await publish_customer_segment(
            database,
            company_id=context.company_id,
            segment_id=segment_id,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.post(
    "/{segment_id}/activate",
    response_model=CustomerSegmentActivationResponse,
)
async def activate_segment(
    segment_id: UUID,
    payload: CustomerSegmentActivationRequest,
    principal: CanActivate,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerSegmentActivationResponse:
    context = get_request_context(principal)
    try:
        response = await activate_customer_segment(
            database,
            company_id=context.company_id,
            segment_id=segment_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.get("/search/profiles", response_model=CustomerProfileSearchResponse)
async def search_profiles(
    principal: CanView,
    _: ActiveCRM,
    database: DatabaseSession,
    q: str = Query(min_length=2, max_length=160),
    limit: int = Query(default=25, ge=1, le=50),
) -> CustomerProfileSearchResponse:
    context = get_request_context(principal)
    return await search_customer_profiles(
        database,
        company_id=context.company_id,
        query=q,
        limit=limit,
    )
