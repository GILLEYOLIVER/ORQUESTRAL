from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.crm.customer_governance_schemas import (
    CustomerLineageCreate,
    CustomerLineageResponse,
    CustomerMatchRuleCreate,
    CustomerMatchRuleResponse,
    CustomerMatchScanResponse,
    CustomerMergeCaseResponse,
    CustomerMergeDecision,
    CustomerMergeRevert,
)
from app.modules.crm.customer_governance_service import (
    create_match_rule,
    decide_merge_case,
    list_lineage,
    list_match_rules,
    list_merge_cases,
    publish_match_rule,
    record_lineage,
    revert_merge_case,
    scan_match_candidates,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(prefix="/crm/customer-data", tags=["crm-customer-data"])

ActiveCRM = Annotated[Principal, Depends(require_active_module("crm"))]
CanViewCustomerData = Annotated[
    Principal,
    Depends(require_permission("crm.contacts.view")),
]
CanManageCustomerData = Annotated[
    Principal,
    Depends(require_permission("crm.contacts.update")),
]


def _http_error(exc: LookupError | ValueError) -> HTTPException:
    return HTTPException(
        status_code=404 if isinstance(exc, LookupError) else 409,
        detail=str(exc),
    )


@router.get("/match-rules", response_model=list[CustomerMatchRuleResponse])
async def get_match_rules(
    principal: CanViewCustomerData,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[CustomerMatchRuleResponse]:
    context = get_request_context(principal)
    return await list_match_rules(database, company_id=context.company_id)


@router.post(
    "/match-rules",
    response_model=CustomerMatchRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_match_rule(
    payload: CustomerMatchRuleCreate,
    principal: CanManageCustomerData,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerMatchRuleResponse:
    context = get_request_context(principal)
    response = await create_match_rule(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        payload=payload,
    )
    await database.commit()
    return response


@router.post(
    "/match-rules/{rule_id}/publish",
    response_model=CustomerMatchRuleResponse,
)
async def post_publish_match_rule(
    rule_id: UUID,
    principal: CanManageCustomerData,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerMatchRuleResponse:
    context = get_request_context(principal)
    try:
        response = await publish_match_rule(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            rule_id=rule_id,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.post("/matches/scan", response_model=CustomerMatchScanResponse)
async def post_match_scan(
    principal: CanManageCustomerData,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerMatchScanResponse:
    context = get_request_context(principal)
    try:
        response = await scan_match_candidates(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.get("/merge-cases", response_model=list[CustomerMergeCaseResponse])
async def get_merge_cases(
    principal: CanViewCustomerData,
    _: ActiveCRM,
    database: DatabaseSession,
    case_status: Annotated[
        Literal["pending", "approved", "rejected", "reverted"] | None,
        Query(alias="status"),
    ] = None,
) -> list[CustomerMergeCaseResponse]:
    context = get_request_context(principal)
    return await list_merge_cases(
        database,
        company_id=context.company_id,
        case_status=case_status,
    )


@router.post(
    "/merge-cases/{case_id}/decision",
    response_model=CustomerMergeCaseResponse,
)
async def post_merge_decision(
    case_id: UUID,
    payload: CustomerMergeDecision,
    principal: CanManageCustomerData,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerMergeCaseResponse:
    context = get_request_context(principal)
    try:
        response = await decide_merge_case(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            case_id=case_id,
            decision=payload.decision,
            note=payload.note,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.post(
    "/merge-cases/{case_id}/revert",
    response_model=CustomerMergeCaseResponse,
)
async def post_merge_revert(
    case_id: UUID,
    payload: CustomerMergeRevert,
    principal: CanManageCustomerData,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerMergeCaseResponse:
    context = get_request_context(principal)
    try:
        response = await revert_merge_case(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            case_id=case_id,
            note=payload.note,
        )
    except (LookupError, ValueError) as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response


@router.get(
    "/profiles/{profile_id}/lineage",
    response_model=list[CustomerLineageResponse],
)
async def get_profile_lineage(
    profile_id: UUID,
    principal: CanViewCustomerData,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[CustomerLineageResponse]:
    context = get_request_context(principal)
    return await list_lineage(
        database,
        company_id=context.company_id,
        profile_id=profile_id,
    )


@router.post(
    "/profiles/{profile_id}/lineage",
    response_model=CustomerLineageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_profile_lineage(
    profile_id: UUID,
    payload: CustomerLineageCreate,
    principal: CanManageCustomerData,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerLineageResponse:
    context = get_request_context(principal)
    try:
        response = await record_lineage(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            profile_id=profile_id,
            payload=payload,
        )
    except LookupError as exc:
        raise _http_error(exc) from exc
    await database.commit()
    return response
