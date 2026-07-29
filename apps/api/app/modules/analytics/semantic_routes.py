from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.analytics.semantic_models import (
    AnalyticsDashboardDefinition,
    AnalyticsMetricDefinition,
    AnalyticsReportDefinition,
)
from app.modules.analytics.semantic_schemas import (
    DashboardCreate,
    DashboardResponse,
    MetricCreate,
    MetricResponse,
    ReportCreate,
    ReportExecution,
    ReportResponse,
)
from app.modules.analytics.semantic_service import SemanticQueryError, execute_report
from app.modules.authorization.service import record_authorization_audit

router = APIRouter(prefix="/analytics", tags=["analytics"])
CanView = Annotated[Principal, Depends(require_permission("analytics.view"))]
CanManage = Annotated[
    Principal, Depends(require_permission("analytics.indicators.manage"))
]


@router.get("/metrics", response_model=list[MetricResponse])
async def metrics(principal: CanView, database: DatabaseSession) -> list[MetricResponse]:
    context = get_request_context(principal)
    rows = list(
        await database.scalars(
            select(AnalyticsMetricDefinition)
            .where(AnalyticsMetricDefinition.company_id == context.company_id)
            .order_by(AnalyticsMetricDefinition.name)
        )
    )
    return [MetricResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/metrics", response_model=MetricResponse, status_code=status.HTTP_201_CREATED)
async def create_metric(
    payload: MetricCreate, principal: CanManage, database: DatabaseSession
) -> MetricResponse:
    context = get_request_context(principal)
    metric = AnalyticsMetricDefinition(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **payload.model_dump(mode="json"),
    )
    database.add(metric)
    try:
        await database.flush()
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="Código de métrica já utilizado.") from error
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="analytics.metric.created",
        target_type="analytics_metric_definition",
        target_id=metric.id,
    )
    await database.commit()
    await database.refresh(metric)
    return MetricResponse.model_validate(metric, from_attributes=True)


@router.get("/reports", response_model=list[ReportResponse])
async def reports(principal: CanView, database: DatabaseSession) -> list[ReportResponse]:
    context = get_request_context(principal)
    rows = list(
        await database.scalars(
            select(AnalyticsReportDefinition)
            .where(AnalyticsReportDefinition.company_id == context.company_id)
            .order_by(AnalyticsReportDefinition.updated_at.desc())
        )
    )
    return [ReportResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    payload: ReportCreate, principal: CanManage, database: DatabaseSession
) -> ReportResponse:
    context = get_request_context(principal)
    report = AnalyticsReportDefinition(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **payload.model_dump(mode="json"),
    )
    database.add(report)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="analytics.report.created",
        target_type="analytics_report_definition",
        target_id=report.id,
    )
    await database.commit()
    await database.refresh(report)
    return ReportResponse.model_validate(report, from_attributes=True)


@router.post("/reports/{report_id}/publish", response_model=ReportResponse)
async def publish_report(
    report_id: UUID, principal: CanManage, database: DatabaseSession
) -> ReportResponse:
    context = get_request_context(principal)
    report = await database.scalar(
        select(AnalyticsReportDefinition).where(
            AnalyticsReportDefinition.id == report_id,
            AnalyticsReportDefinition.company_id == context.company_id,
        )
    )
    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")
    report.status = "published"
    report.version += 1
    await database.commit()
    await database.refresh(report)
    return ReportResponse.model_validate(report, from_attributes=True)


@router.post("/reports/{report_id}/execute", response_model=ReportExecution)
async def run_report(
    report_id: UUID, principal: CanView, database: DatabaseSession
) -> ReportExecution:
    context = get_request_context(principal)
    report = await database.scalar(
        select(AnalyticsReportDefinition).where(
            AnalyticsReportDefinition.id == report_id,
            AnalyticsReportDefinition.company_id == context.company_id,
        )
    )
    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")
    try:
        result = await execute_report(
            database,
            company_id=context.company_id,
            user_id=context.user_id,
            report=report,
        )
    except SemanticQueryError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    await database.commit()
    return result


@router.get("/dashboards", response_model=list[DashboardResponse])
async def dashboards(
    principal: CanView, database: DatabaseSession
) -> list[DashboardResponse]:
    context = get_request_context(principal)
    rows = list(
        await database.scalars(
            select(AnalyticsDashboardDefinition)
            .where(
                AnalyticsDashboardDefinition.company_id == context.company_id,
                AnalyticsDashboardDefinition.active.is_(True),
            )
            .order_by(AnalyticsDashboardDefinition.name)
        )
    )
    return [DashboardResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post(
    "/dashboards",
    response_model=DashboardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dashboard(
    payload: DashboardCreate, principal: CanManage, database: DatabaseSession
) -> DashboardResponse:
    context = get_request_context(principal)
    report_ids = {widget.report_id for widget in payload.layout}
    if report_ids:
        available = set(
            await database.scalars(
                select(AnalyticsReportDefinition.id).where(
                    AnalyticsReportDefinition.company_id == context.company_id,
                    AnalyticsReportDefinition.id.in_(report_ids),
                )
            )
        )
        if available != report_ids:
            raise HTTPException(
                status_code=422, detail="O painel contém relatório indisponível."
            )
    dashboard = AnalyticsDashboardDefinition(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **payload.model_dump(mode="json"),
    )
    database.add(dashboard)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="analytics.dashboard.created",
        target_type="analytics_dashboard_definition",
        target_id=dashboard.id,
    )
    await database.commit()
    await database.refresh(dashboard)
    return DashboardResponse.model_validate(dashboard, from_attributes=True)
