from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.crm.customer_ingestion_schemas import (
    CustomerDeadLetterResponse,
    CustomerIngestionJobCreate,
    CustomerIngestionJobResponse,
    CustomerIngestionRecordResponse,
    CustomerIngestionReprocess,
    CustomerQualityRuleSetCreate,
    CustomerQualityRuleSetResponse,
)
from app.modules.crm.customer_ingestion_service import (
    create_quality_rule_set,
    ingest_customer_records,
    list_dead_letters,
    list_ingestion_jobs,
    list_quality_rule_sets,
    publish_quality_rule_set,
    reprocess_dead_letter,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(prefix="/crm/customer-data/ingestion", tags=["crm-customer-ingestion"])

ActiveCRM = Annotated[Principal, Depends(require_active_module("crm"))]
CanView = Annotated[Principal, Depends(require_permission("crm.contacts.view"))]
CanManage = Annotated[Principal, Depends(require_permission("crm.contacts.update"))]


def _http_error(exc: LookupError | ValueError) -> HTTPException:
    return HTTPException(
        status_code=404 if isinstance(exc, LookupError) else 409,
        detail=str(exc),
    )


@router.get("/quality-rules", response_model=list[CustomerQualityRuleSetResponse])
async def get_quality_rules(
    principal: CanView,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[CustomerQualityRuleSetResponse]:
    context = get_request_context(principal)
    return await list_quality_rule_sets(database, company_id=context.company_id)


@router.post(
    "/quality-rules",
    response_model=CustomerQualityRuleSetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_quality_rule(
    payload: CustomerQualityRuleSetCreate,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerQualityRuleSetResponse:
    context = get_request_context(principal)
    response = await create_quality_rule_set(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        payload=payload,
    )
    await database.commit()
    return response


@router.post(
    "/quality-rules/{rule_set_id}/publish",
    response_model=CustomerQualityRuleSetResponse,
)
async def post_publish_quality_rule(
    rule_set_id: UUID,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerQualityRuleSetResponse:
    context = get_request_context(principal)
    try:
        response = await publish_quality_rule_set(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            rule_set_id=rule_set_id,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.get("/jobs", response_model=list[CustomerIngestionJobResponse])
async def get_ingestion_jobs(
    principal: CanView,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[CustomerIngestionJobResponse]:
    context = get_request_context(principal)
    return await list_ingestion_jobs(database, company_id=context.company_id)


@router.post(
    "/jobs",
    response_model=CustomerIngestionJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_ingestion_job(
    payload: CustomerIngestionJobCreate,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerIngestionJobResponse:
    context = get_request_context(principal)
    try:
        response = await ingest_customer_records(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.get("/dead-letters", response_model=list[CustomerDeadLetterResponse])
async def get_dead_letters(
    principal: CanView,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[CustomerDeadLetterResponse]:
    context = get_request_context(principal)
    return await list_dead_letters(database, company_id=context.company_id)


@router.post(
    "/dead-letters/{record_id}/reprocess",
    response_model=CustomerIngestionRecordResponse,
)
async def post_dead_letter_reprocess(
    record_id: UUID,
    payload: CustomerIngestionReprocess,
    principal: CanManage,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerIngestionRecordResponse:
    context = get_request_context(principal)
    try:
        response = await reprocess_dead_letter(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            record_id=record_id,
            payload=payload,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response
