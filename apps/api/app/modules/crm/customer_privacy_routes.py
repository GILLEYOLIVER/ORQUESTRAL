from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.crm.customer_privacy_schemas import (
    CustomerPrivacyDecisionRequest,
    CustomerPrivacyLegalHoldRequest,
    CustomerPrivacyRequestCreate,
    CustomerPrivacyRequestResponse,
    CustomerPrivacySummaryResponse,
)
from app.modules.crm.customer_privacy_service import (
    create_customer_privacy_request,
    decide_customer_privacy_request,
    execute_customer_privacy_request,
    get_customer_privacy_summary,
    list_customer_privacy_requests,
    set_customer_privacy_legal_hold,
    verify_customer_privacy_identity,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(prefix="/crm/customer-data/privacy", tags=["customer-privacy"])

ActiveCRM = Annotated[Principal, Depends(require_active_module("crm"))]
CanView = Annotated[Principal, Depends(require_permission("crm.contacts.view"))]
CanManage = Annotated[Principal, Depends(require_permission("crm.contacts.update"))]
CanErase = Annotated[Principal, Depends(require_permission("crm.contacts.delete"))]


def _http_error(exc: LookupError | ValueError) -> HTTPException:
    return HTTPException(
        status_code=404 if isinstance(exc, LookupError) else 409,
        detail=str(exc),
    )


@router.get("/summary", response_model=CustomerPrivacySummaryResponse)
async def privacy_summary(
    principal: CanView,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerPrivacySummaryResponse:
    context = get_request_context(principal)
    return await get_customer_privacy_summary(
        database,
        company_id=context.company_id,
    )


@router.get("/requests", response_model=list[CustomerPrivacyRequestResponse])
async def privacy_requests(
    principal: CanView,
    _: ActiveCRM,
    database: DatabaseSession,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[CustomerPrivacyRequestResponse]:
    context = get_request_context(principal)
    return await list_customer_privacy_requests(
        database,
        company_id=context.company_id,
        limit=limit,
    )


@router.post(
    "/requests",
    response_model=CustomerPrivacyRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_privacy_request(
    payload: CustomerPrivacyRequestCreate,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerPrivacyRequestResponse:
    context = get_request_context(principal)
    try:
        response = await create_customer_privacy_request(
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
    "/requests/{request_id}/verify",
    response_model=CustomerPrivacyRequestResponse,
)
async def verify_privacy_request(
    request_id: UUID,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerPrivacyRequestResponse:
    context = get_request_context(principal)
    try:
        response = await verify_customer_privacy_identity(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            request_id=request_id,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.post(
    "/requests/{request_id}/decision",
    response_model=CustomerPrivacyRequestResponse,
)
async def decide_privacy_request(
    request_id: UUID,
    payload: CustomerPrivacyDecisionRequest,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerPrivacyRequestResponse:
    context = get_request_context(principal)
    try:
        response = await decide_customer_privacy_request(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            request_id=request_id,
            payload=payload,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.post(
    "/requests/{request_id}/legal-hold",
    response_model=CustomerPrivacyRequestResponse,
)
async def privacy_legal_hold(
    request_id: UUID,
    payload: CustomerPrivacyLegalHoldRequest,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerPrivacyRequestResponse:
    context = get_request_context(principal)
    try:
        response = await set_customer_privacy_legal_hold(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            request_id=request_id,
            payload=payload,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.post(
    "/requests/{request_id}/execute",
    response_model=CustomerPrivacyRequestResponse,
)
async def execute_privacy_request(
    request_id: UUID,
    principal: CanErase,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerPrivacyRequestResponse:
    context = get_request_context(principal)
    try:
        response = await execute_customer_privacy_request(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            request_id=request_id,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response

