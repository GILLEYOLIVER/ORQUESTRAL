from __future__ import annotations

from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.crm.sales_schemas import (
    CRMAccountCreate,
    CRMAccountResponse,
    CRMLeadConversionCreate,
    CRMLeadConversionResponse,
    CRMLeadCreate,
    CRMLeadQualification,
    CRMLeadResponse,
    CRMLeadUpdate,
)
from app.modules.crm.sales_service import (
    SalesServiceError,
    convert_lead,
    create_account,
    create_lead,
    list_accounts,
    list_leads,
    qualify_lead,
    update_lead,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(prefix="/crm/sales", tags=["crm-sales"])

ActiveCRM = Annotated[Principal, Depends(require_active_module("crm"))]
CanViewAccounts = Annotated[Principal, Depends(require_permission("crm.accounts.view"))]
CanManageAccounts = Annotated[Principal, Depends(require_permission("crm.accounts.manage"))]
CanViewLeads = Annotated[Principal, Depends(require_permission("crm.leads.view"))]
CanManageLeads = Annotated[Principal, Depends(require_permission("crm.leads.manage"))]
CanQualifyLeads = Annotated[Principal, Depends(require_permission("crm.leads.qualify"))]
CanConvertLeads = Annotated[Principal, Depends(require_permission("crm.leads.convert"))]


def _raise_service_error(error: SalesServiceError) -> NoReturn:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/accounts", response_model=list[CRMAccountResponse])
async def accounts(
    principal: CanViewAccounts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[CRMAccountResponse]:
    context = get_request_context(principal)
    return await list_accounts(database, company_id=context.company_id)


@router.post(
    "/accounts",
    response_model=CRMAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_account(
    payload: CRMAccountCreate,
    principal: CanManageAccounts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMAccountResponse:
    context = get_request_context(principal)
    try:
        return await create_account(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except SalesServiceError as error:
        _raise_service_error(error)


@router.get("/leads", response_model=list[CRMLeadResponse])
async def leads(
    principal: CanViewLeads,
    _: ActiveCRM,
    database: DatabaseSession,
    lead_status: Annotated[
        Literal["new", "working", "qualified", "converted", "disqualified"] | None,
        Query(alias="status"),
    ] = None,
) -> list[CRMLeadResponse]:
    context = get_request_context(principal)
    return await list_leads(
        database,
        company_id=context.company_id,
        status_filter=lead_status,
    )


@router.post(
    "/leads",
    response_model=CRMLeadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_lead(
    payload: CRMLeadCreate,
    principal: CanManageLeads,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMLeadResponse:
    context = get_request_context(principal)
    try:
        return await create_lead(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except SalesServiceError as error:
        _raise_service_error(error)


@router.patch("/leads/{lead_id}", response_model=CRMLeadResponse)
async def change_lead(
    lead_id: UUID,
    payload: CRMLeadUpdate,
    principal: CanManageLeads,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMLeadResponse:
    context = get_request_context(principal)
    try:
        return await update_lead(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            lead_id=lead_id,
            payload=payload,
        )
    except SalesServiceError as error:
        _raise_service_error(error)


@router.post("/leads/{lead_id}/qualification", response_model=CRMLeadResponse)
async def decide_lead(
    lead_id: UUID,
    payload: CRMLeadQualification,
    principal: CanQualifyLeads,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMLeadResponse:
    context = get_request_context(principal)
    try:
        return await qualify_lead(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            lead_id=lead_id,
            payload=payload,
        )
    except SalesServiceError as error:
        _raise_service_error(error)


@router.post(
    "/leads/{lead_id}/conversion",
    response_model=CRMLeadConversionResponse,
)
async def run_conversion(
    lead_id: UUID,
    payload: CRMLeadConversionCreate,
    principal: CanConvertLeads,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMLeadConversionResponse:
    context = get_request_context(principal)
    try:
        return await convert_lead(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            lead_id=lead_id,
            payload=payload,
        )
    except SalesServiceError as error:
        _raise_service_error(error)
