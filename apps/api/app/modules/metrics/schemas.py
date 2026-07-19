from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from app.core.schemas import StrictSchema


class MetricTotals(StrictSchema):
    automation_executions: int = 0
    automation_success: int = 0
    automation_failure: int = 0
    time_saved_minutes: float = 0
    agent_uses: int = 0
    tokens: int = 0
    ai_cost_usd: float = 0
    integration_failures: int = 0
    active_users: int = 0
    documents_processed: int = 0
    pending_approvals: int = 0


class MetricSeriesPoint(MetricTotals):
    date: date


class TopAgent(StrictSchema):
    id: UUID
    name: str
    uses: int
    tokens: int
    cost_usd: float


class MetricPeriod(StrictSchema):
    start: date
    end: date


class DashboardResponse(StrictSchema):
    period: MetricPeriod
    totals: MetricTotals
    series: list[MetricSeriesPoint]
    top_agents: list[TopAgent]
    generated_at: datetime
    cached: bool = False
