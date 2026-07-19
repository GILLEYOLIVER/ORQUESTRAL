from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select

from app.core.dependencies import DatabaseSession, RedisClient
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.agents.models import Agent
from app.modules.metrics.aggregation import aggregate_metrics
from app.modules.metrics.calculations import calculate_dashboard
from app.modules.metrics.models import MetricDailySummary
from app.modules.metrics.reports import csv_report, pdf_report, xlsx_report
from app.modules.metrics.schemas import DashboardResponse, MetricPeriod

router = APIRouter(prefix="/metrics", tags=["metrics"])
CanViewMetrics = Annotated[Principal, Depends(require_permission("metrics.view"))]
CanExportMetrics = Annotated[Principal, Depends(require_permission("metrics.export"))]


def _period(start: date | None, end: date | None) -> tuple[date, date]:
    final = end or date.today()
    initial = start or (final - timedelta(days=29))
    if initial > final:
        raise HTTPException(
            status_code=422, detail="A data inicial deve ser anterior a data final."
        )
    if (final - initial).days > 366:
        raise HTTPException(status_code=422, detail="O periodo maximo e de 366 dias.")
    return initial, final


async def _dashboard(
    *,
    company_id: UUID,
    database: DatabaseSession,
    redis: RedisClient,
    start: date,
    end: date,
    module: str | None,
    agent_id: UUID | None,
    workflow_id: UUID | None,
    allow_cache: bool = True,
) -> DashboardResponse:
    cache_key = (
        f"metrics:{company_id}:{start}:{end}:{module or '-'}:{agent_id or '-'}:{workflow_id or '-'}"
    )
    if allow_cache:
        cached = await redis.get(cache_key)
        if cached:
            parsed = DashboardResponse.model_validate_json(cached)
            return parsed.model_copy(update={"cached": True})
    statement = select(MetricDailySummary).where(
        MetricDailySummary.company_id == company_id,
        MetricDailySummary.metric_date >= start,
        MetricDailySummary.metric_date <= end,
    )
    if module:
        statement = statement.where(MetricDailySummary.module == module)
    if agent_id:
        statement = statement.where(MetricDailySummary.agent_id == agent_id)
    if workflow_id:
        statement = statement.where(MetricDailySummary.workflow_id == workflow_id)
    rows = list(await database.scalars(statement))
    if not rows:
        await aggregate_metrics(days=max(90, (end - start).days + 1))
        rows = list(await database.scalars(statement))
    agent_ids = {row.agent_id for row in rows if row.agent_id is not None}
    agent_names: dict[str, str] = {}
    if agent_ids:
        agents = list(
            await database.scalars(
                select(Agent).where(Agent.company_id == company_id, Agent.id.in_(agent_ids))
            )
        )
        agent_names = {str(agent.id): agent.name for agent in agents}
    calculated = calculate_dashboard(rows, agent_names, start, end)
    response = DashboardResponse(
        period=MetricPeriod(start=start, end=end),
        totals=calculated["totals"],
        series=calculated["series"],
        top_agents=calculated["top_agents"],
        generated_at=calculated["generated_at"] or datetime.now(UTC),
        cached=False,
    )
    await redis.setex(cache_key, 300, response.model_dump_json())
    return response


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    principal: CanViewMetrics,
    database: DatabaseSession,
    redis: RedisClient,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    module: str | None = Query(default=None, max_length=40),
    agent_id: UUID | None = None,
    workflow_id: UUID | None = None,
) -> DashboardResponse:
    context = get_request_context(principal)
    start, end = _period(from_date, to_date)
    return await _dashboard(
        company_id=context.company_id,
        database=database,
        redis=redis,
        start=start,
        end=end,
        module=module,
        agent_id=agent_id,
        workflow_id=workflow_id,
    )


@router.post("/aggregate")
async def aggregate_now(principal: CanExportMetrics, redis: RedisClient) -> dict[str, int | str]:
    del principal
    rows = await aggregate_metrics()
    async for key in redis.scan_iter(match="metrics:*"):
        await redis.delete(key)
    return {"status": "ok", "rows": rows}


@router.get("/export")
async def export_metrics(
    principal: CanExportMetrics,
    database: DatabaseSession,
    redis: RedisClient,
    format: Literal["csv", "xlsx", "pdf"] = "csv",
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    module: str | None = Query(default=None, max_length=40),
    agent_id: UUID | None = None,
    workflow_id: UUID | None = None,
) -> Response:
    context = get_request_context(principal)
    start, end = _period(from_date, to_date)
    data = await _dashboard(
        company_id=context.company_id,
        database=database,
        redis=redis,
        start=start,
        end=end,
        module=module,
        agent_id=agent_id,
        workflow_id=workflow_id,
    )
    if format == "csv":
        content, media_type = csv_report(data), "text/csv; charset=utf-8"
    elif format == "xlsx":
        content, media_type = (
            xlsx_report(data),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        content, media_type = pdf_report(data), "application/pdf"
    filename = f"orkestral-metricas-{start}-{end}.{format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
