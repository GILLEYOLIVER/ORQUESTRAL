from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from app.core.schemas import StrictSchema

HealthLevel = Literal["healthy", "attention", "critical"]
ForecastCategory = Literal["pipeline", "best_case", "commit"]


class OpportunityInsightResponse(StrictSchema):
    opportunity_id: UUID
    title: str
    amount: Decimal
    probability: int
    weighted_amount: Decimal
    expected_close_date: date | None
    last_activity_at: datetime | None
    stale_days: int
    activity_count: int
    health_score: int
    health_level: HealthLevel
    forecast_category: ForecastCategory
    has_proposal: bool
    has_published_quote: bool
    has_accepted_quote: bool
    reasons: list[str]
    next_best_action: str


class SalesForecastResponse(StrictSchema):
    generated_at: datetime
    currency: str
    opportunity_count: int
    at_risk_count: int
    overdue_count: int
    total_open_amount: Decimal
    weighted_amount: Decimal
    pipeline_amount: Decimal
    best_case_amount: Decimal
    commit_amount: Decimal
    opportunities: list[OpportunityInsightResponse]
