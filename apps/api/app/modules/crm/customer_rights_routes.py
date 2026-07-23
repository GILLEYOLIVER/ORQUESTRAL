from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.crm.customer_rights_schemas import (
    CustomerCorrectionRequest,
    CustomerCorrectionResponse,
    CustomerProcessingRestrictionCreate,
    CustomerProcessingRestrictionResponse,
    CustomerRightsSummaryResponse,
    CustomerSubjectExportResponse,
)
from app.modules.crm.customer_rights_service import (
    correct_customer_subject,
    export_customer_subject,
    get_customer_rights_summary,
    list_processing_restrictions,
    release_customer_processing_restriction,
    restrict_customer_processing,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(prefix="/crm/customer-data/rights", tags=["customer-rights"])

ActiveCRM = Annotated[Principal, Depends(require_active_module("crm"))]
CanView = Annotated[Principal, Depends(require_permission("crm.contacts.view"))]
CanExport = Annotated[Principal, Depends(require_permission("crm.contacts.export"))]
CanManage = Annotated[Principal, Depends(require_permission("crm.contacts.update"))]


def _http_error(exc: LookupError | ValueError) -> HTTPException:
    return HTTPException(
        status_code=404 if isinstance(exc, LookupError) else 409,
        detail=str(exc),
    )


@router.get("/summary", response_model=CustomerRightsSummaryResponse)
async def customer_rights_summary(
    principal: CanView,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerRightsSummaryResponse:
    context = get_request_context(principal)
    return await get_customer_rights_summary(database, company_id=context.company_id)


@router.get(
    "/restrictions",
    response_model=list[CustomerProcessingRestrictionResponse],
)
async def customer_processing_restrictions(
    principal: CanView,
    _: ActiveCRM,
    database: DatabaseSession,
    active_only: bool = Query(default=True),
) -> list[CustomerProcessingRestrictionResponse]:
    context = get_request_context(principal)
    return await list_processing_restrictions(
        database,
        company_id=context.company_id,
        active_only=active_only,
    )


@router.post(
    "/subjects/{profile_id}/restriction",
    response_model=CustomerProcessingRestrictionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_customer_processing_restriction(
    profile_id: UUID,
    payload: CustomerProcessingRestrictionCreate,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerProcessingRestrictionResponse:
    context = get_request_context(principal)
    try:
        response = await restrict_customer_processing(
            database,
            company_id=context.company_id,
            profile_id=profile_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.delete(
    "/subjects/{profile_id}/restriction",
    response_model=CustomerProcessingRestrictionResponse,
)
async def release_customer_processing(
    profile_id: UUID,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerProcessingRestrictionResponse:
    context = get_request_context(principal)
    try:
        response = await release_customer_processing_restriction(
            database,
            company_id=context.company_id,
            profile_id=profile_id,
            actor_user_id=context.user_id,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.patch(
    "/subjects/{profile_id}",
    response_model=CustomerCorrectionResponse,
)
async def correct_customer_data(
    profile_id: UUID,
    payload: CustomerCorrectionRequest,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerCorrectionResponse:
    context = get_request_context(principal)
    try:
        response = await correct_customer_subject(
            database,
            company_id=context.company_id,
            profile_id=profile_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.post(
    "/subjects/{profile_id}/export",
    response_model=CustomerSubjectExportResponse,
)
async def export_customer_data(
    profile_id: UUID,
    response: Response,
    principal: CanExport,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerSubjectExportResponse:
    context = get_request_context(principal)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    try:
        package = await export_customer_subject(
            database,
            company_id=context.company_id,
            profile_id=profile_id,
            actor_user_id=context.user_id,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return package
