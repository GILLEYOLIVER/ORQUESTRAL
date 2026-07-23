from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.crm.sales_governance_schemas import (
    OpportunityTerritoryAssignment,
    RenewalPlanCreate,
    RenewalPlanResponse,
    RenewalStatusUpdate,
    SalesGoalCreate,
    SalesGoalResponse,
    SalesGovernanceDashboard,
    TerritoryCreate,
    TerritoryResponse,
)
from app.modules.crm.sales_governance_service import (
    SalesGovernanceError,
    assign_opportunity_territory,
    build_sales_governance_dashboard,
    create_renewal_plan,
    create_sales_goal,
    create_territory,
    list_renewal_plans,
    list_sales_goals,
    list_territories,
    update_renewal_status,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(
    prefix="/crm/sales/governance",
    tags=["crm-sales-governance"],
)

ActiveCRM = Annotated[Principal, Depends(require_active_module("crm"))]
CanViewPipeline = Annotated[
    Principal,
    Depends(require_permission("crm.pipeline.view")),
]
CanManagePipeline = Annotated[
    Principal,
    Depends(require_permission("crm.pipeline.manage")),
]


def _raise(error: SalesGovernanceError) -> NoReturn:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/dashboard", response_model=SalesGovernanceDashboard)
async def governance_dashboard(
    principal: CanViewPipeline,
    _: ActiveCRM,
    database: DatabaseSession,
) -> SalesGovernanceDashboard:
    context = get_request_context(principal)
    return await build_sales_governance_dashboard(
        database,
        company_id=context.company_id,
    )


@router.get("/territories", response_model=list[TerritoryResponse])
async def territories(
    principal: CanViewPipeline,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[TerritoryResponse]:
    context = get_request_context(principal)
    return await list_territories(database, company_id=context.company_id)


@router.post(
    "/territories",
    response_model=TerritoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_territory(
    payload: TerritoryCreate,
    principal: CanManagePipeline,
    _: ActiveCRM,
    database: DatabaseSession,
) -> TerritoryResponse:
    context = get_request_context(principal)
    try:
        return await create_territory(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except SalesGovernanceError as error:
        _raise(error)


@router.put(
    "/opportunities/{opportunity_id}/territory",
    response_model=TerritoryResponse | None,
)
async def set_opportunity_territory(
    opportunity_id: UUID,
    payload: OpportunityTerritoryAssignment,
    principal: CanManagePipeline,
    _: ActiveCRM,
    database: DatabaseSession,
) -> TerritoryResponse | None:
    context = get_request_context(principal)
    try:
        return await assign_opportunity_territory(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            opportunity_id=opportunity_id,
            payload=payload,
        )
    except SalesGovernanceError as error:
        _raise(error)


@router.get("/goals", response_model=list[SalesGoalResponse])
async def goals(
    principal: CanViewPipeline,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[SalesGoalResponse]:
    context = get_request_context(principal)
    return await list_sales_goals(database, company_id=context.company_id)


@router.post(
    "/goals",
    response_model=SalesGoalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_goal(
    payload: SalesGoalCreate,
    principal: CanManagePipeline,
    _: ActiveCRM,
    database: DatabaseSession,
) -> SalesGoalResponse:
    context = get_request_context(principal)
    try:
        return await create_sales_goal(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except SalesGovernanceError as error:
        _raise(error)


@router.get("/renewals", response_model=list[RenewalPlanResponse])
async def renewals(
    principal: CanViewPipeline,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[RenewalPlanResponse]:
    context = get_request_context(principal)
    return await list_renewal_plans(database, company_id=context.company_id)


@router.post(
    "/renewals",
    response_model=RenewalPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_renewal(
    payload: RenewalPlanCreate,
    principal: CanManagePipeline,
    _: ActiveCRM,
    database: DatabaseSession,
) -> RenewalPlanResponse:
    context = get_request_context(principal)
    try:
        return await create_renewal_plan(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except SalesGovernanceError as error:
        _raise(error)


@router.post(
    "/renewals/{renewal_id}/status",
    response_model=RenewalPlanResponse,
)
async def change_renewal_status(
    renewal_id: UUID,
    payload: RenewalStatusUpdate,
    principal: CanManagePipeline,
    _: ActiveCRM,
    database: DatabaseSession,
) -> RenewalPlanResponse:
    context = get_request_context(principal)
    try:
        return await update_renewal_status(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            renewal_id=renewal_id,
            payload=payload,
        )
    except SalesGovernanceError as error:
        _raise(error)
