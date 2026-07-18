from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.modules.metrics.calculations import calculate_dashboard
from app.modules.metrics.reports import csv_report, pdf_report, xlsx_report
from app.modules.metrics.schemas import DashboardResponse, MetricPeriod


def row(key: str, value: int | float, *, agent_id=None):
    return SimpleNamespace(metric_key=key, numeric_value=Decimal(str(value)), metric_date=date(2026, 7, 18), agent_id=agent_id, generated_at=datetime(2026, 7, 18, tzinfo=timezone.utc))


def test_dashboard_calculation_aggregates_totals_series_and_agents() -> None:
    agent_id = uuid4()
    result = calculate_dashboard([
        row("automation.executions", 3),
        row("automation.success", 2),
        row("automation.failure", 1),
        row("agent.uses", 4, agent_id=agent_id),
        row("agent.tokens", 900, agent_id=agent_id),
        row("agent.cost_usd", 0.42, agent_id=agent_id),
    ], {str(agent_id): "Agente Comercial"}, date(2026, 7, 18), date(2026, 7, 18))
    assert result["totals"]["automation_executions"] == 3
    assert result["totals"]["automation_success"] == 2
    assert result["top_agents"][0]["name"] == "Agente Comercial"
    assert result["top_agents"][0]["tokens"] == 900


def test_reports_generate_valid_csv_xlsx_and_pdf() -> None:
    data = DashboardResponse(
        period=MetricPeriod(start=date(2026, 7, 1), end=date(2026, 7, 18)),
        totals={"automation_executions": 2, "automation_success": 2},
        series=[{"date": date(2026, 7, 18), "automation_executions": 2, "automation_success": 2}],
        top_agents=[],
        generated_at=datetime.now(timezone.utc),
    )
    assert csv_report(data).startswith(b"\xef\xbb\xbf")
    assert xlsx_report(data).startswith(b"PK")
    assert pdf_report(data).startswith(b"%PDF")
