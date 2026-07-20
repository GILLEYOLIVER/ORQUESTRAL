from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.schemas import StrictSchema

IndicatorUnit = Literal["number", "currency", "percent", "hours", "days"]
IndicatorDirection = Literal["higher_better", "lower_better", "neutral"]
TargetStatus = Literal["achieved", "behind", "no_target", "no_data"]


class IndicatorCreate(StrictSchema):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    name: str = Field(min_length=2, max_length=140)
    description: str | None = Field(default=None, max_length=2000)
    category: str = Field(default="Geral", min_length=2, max_length=80)
    unit: IndicatorUnit = "number"
    direction: IndicatorDirection = "higher_better"
    target_value: Decimal | None = Field(default=None, max_digits=20, decimal_places=4)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().lower()


class IndicatorUpdate(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=140)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, min_length=2, max_length=80)
    unit: IndicatorUnit | None = None
    direction: IndicatorDirection | None = None
    target_value: Decimal | None = Field(default=None, max_digits=20, decimal_places=4)
    active: bool | None = None


class IndicatorResponse(StrictSchema):
    id: UUID
    code: str
    name: str
    description: str | None
    category: str
    unit: IndicatorUnit
    direction: IndicatorDirection
    target_value: Decimal | None
    active: bool
    created_at: datetime
    updated_at: datetime


class MeasurementCreate(StrictSchema):
    period_start: date
    period_end: date
    value: Decimal = Field(max_digits=20, decimal_places=4)
    source: str = Field(default="manual", min_length=2, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_period(self) -> MeasurementCreate:
        if self.period_end < self.period_start:
            raise ValueError("A data final deve ser igual ou posterior a data inicial.")
        return self


class MeasurementResponse(StrictSchema):
    id: UUID
    indicator_id: UUID
    period_start: date
    period_end: date
    value: Decimal
    source: str
    notes: str | None
    created_at: datetime


class IndicatorSnapshot(IndicatorResponse):
    latest_value: Decimal | None = None
    previous_value: Decimal | None = None
    change_percent: Decimal | None = None
    target_progress_percent: Decimal | None = None
    target_status: TargetStatus = "no_data"
    measured_at: date | None = None


class AnalyticsSummary(StrictSchema):
    active_indicators: int = 0
    indicators_with_data: int = 0
    targets_achieved: int = 0
    targets_behind: int = 0


class AnalyticsOverviewResponse(StrictSchema):
    summary: AnalyticsSummary
    indicators: list[IndicatorSnapshot]
    generated_at: datetime
