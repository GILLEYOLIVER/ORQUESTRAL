from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.semantic_models import (
    AnalyticsMetricDefinition,
    AnalyticsReportDefinition,
    AnalyticsReportRun,
)
from app.modules.analytics.semantic_schemas import ReportExecution, SemanticFilter


class SemanticQueryError(ValueError):
    pass


@dataclass(frozen=True)
class DatasetContract:
    table: str
    dimensions: frozenset[str]
    values: frozenset[str]
    filters: frozenset[str]


DATASETS = {
    "commerce.orders": DatasetContract(
        "commerce_orders",
        frozenset({"status", "currency"}),
        frozenset({"total", "subtotal", "discount_total"}),
        frozenset({"status", "currency", "created_at"}),
    ),
    "finance.entries": DatasetContract(
        "financial_entries",
        frozenset({"status", "entry_type", "payment_method"}),
        frozenset({"amount"}),
        frozenset({"status", "entry_type", "due_date", "competence_date"}),
    ),
    "inventory.balances": DatasetContract(
        "inventory_balances",
        frozenset(),
        frozenset({"quantity"}),
        frozenset({"item_id", "location_id"}),
    ),
    "support.tickets": DatasetContract(
        "support_tickets",
        frozenset({"status", "priority", "channel"}),
        frozenset(),
        frozenset({"status", "priority", "channel", "created_at"}),
    ),
}


def compile_semantic_query(
    *,
    dataset: str,
    dimensions: list[str],
    metrics: list[AnalyticsMetricDefinition],
    filters: list[SemanticFilter],
    company_id: UUID,
) -> tuple[str, dict[str, object], list[str]]:
    contract = DATASETS.get(dataset)
    if not contract:
        raise SemanticQueryError("Conjunto de dados não permitido.")
    if any(field not in contract.dimensions for field in dimensions):
        raise SemanticQueryError("Dimensão não permitida para este conjunto.")
    selects = list(dimensions)
    columns = list(dimensions)
    for metric in metrics:
        if metric.dataset != dataset:
            raise SemanticQueryError("A métrica pertence a outro conjunto de dados.")
        if metric.aggregation != "count" and metric.value_field not in contract.values:
            raise SemanticQueryError("Campo de valor não permitido.")
        expression = (
            "COUNT(*)"
            if metric.aggregation == "count"
            else f"{metric.aggregation.upper()}({metric.value_field})"
        )
        selects.append(f'{expression} AS "{metric.code}"')
        columns.append(metric.code)
    params: dict[str, object] = {"company_id": company_id}
    clauses = ["company_id = :company_id"]
    for index, item in enumerate(filters):
        if item.field not in contract.filters:
            raise SemanticQueryError("Filtro não permitido para este conjunto.")
        operator = {"eq": "=", "ne": "!=", "gte": ">=", "lte": "<="}[item.operator]
        parameter = f"filter_{index}"
        clauses.append(f"{item.field} {operator} :{parameter}")
        params[parameter] = item.value
    # Tabela, dimensoes, agregacoes e campos vieram exclusivamente de DATASETS.
    query = f"SELECT {', '.join(selects)} FROM {contract.table}"  # noqa: S608
    query += " WHERE " + " AND ".join(clauses)
    if dimensions:
        query += " GROUP BY " + ", ".join(dimensions)
    query += " ORDER BY 1 LIMIT 500"
    return query, params, columns


async def execute_report(
    database: AsyncSession,
    *,
    company_id: UUID,
    user_id: UUID,
    report: AnalyticsReportDefinition,
) -> ReportExecution:
    metrics = list(
        (
            await database.scalars(
                select(AnalyticsMetricDefinition).where(
                    AnalyticsMetricDefinition.company_id == company_id,
                    AnalyticsMetricDefinition.code.in_(report.metric_codes),
                    AnalyticsMetricDefinition.active.is_(True),
                )
            )
        ).all()
    )
    by_code = {metric.code: metric for metric in metrics}
    if any(code not in by_code for code in report.metric_codes):
        raise SemanticQueryError("Uma ou mais métricas não estão disponíveis.")
    filters = [SemanticFilter.model_validate(item) for item in report.filters]
    query, params, columns = compile_semantic_query(
        dataset=report.dataset,
        dimensions=report.dimensions,
        metrics=[by_code[code] for code in report.metric_codes],
        filters=filters,
        company_id=company_id,
    )
    started = perf_counter()
    result = await database.execute(text(query), params)
    rows = [dict(row) for row in result.mappings().all()]
    duration = int((perf_counter() - started) * 1000)
    database.add(
        AnalyticsReportRun(
            company_id=company_id,
            report_id=report.id,
            executed_by_user_id=user_id,
            status="completed",
            row_count=len(rows),
            duration_ms=duration,
        )
    )
    await database.flush()
    return ReportExecution(
        report_id=report.id,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        duration_ms=duration,
    )
