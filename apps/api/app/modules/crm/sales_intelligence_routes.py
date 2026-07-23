from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.crm.sales_intelligence_schemas import (
    OpportunityInsightResponse,
    SalesForecastResponse,
)
from app.modules.crm.sales_intelligence_service import (
    build_sales_forecast,
    list_opportunity_insights,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(
    prefix="/crm/sales/intelligence",
    tags=["crm-sales-intelligence"],
)

ActiveCRM = Annotated[Principal, Depends(require_active_module("crm"))]
CanViewPipeline = Annotated[
    Principal,
    Depends(require_permission("crm.pipeline.view")),
]


@router.get("/opportunities", response_model=list[OpportunityInsightResponse])
async def opportunity_insights(
    principal: CanViewPipeline,
    _: ActiveCRM,
    database: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[OpportunityInsightResponse]:
    context = get_request_context(principal)
    return await list_opportunity_insights(
        database,
        company_id=context.company_id,
        limit=limit,
    )


@router.get("/forecast", response_model=SalesForecastResponse)
async def sales_forecast(
    principal: CanViewPipeline,
    _: ActiveCRM,
    database: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> SalesForecastResponse:
    context = get_request_context(principal)
    return await build_sales_forecast(
        database,
        company_id=context.company_id,
        limit=limit,
    )
