from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.schemas import StrictSchema

Dataset = Literal[
    "commerce.orders",
    "finance.entries",
    "inventory.balances",
    "support.tickets",
]
Aggregation = Literal["count", "sum", "avg", "min", "max"]


class SemanticFilter(StrictSchema):
    field: str = Field(min_length=1, max_length=80)
    operator: Literal["eq", "ne", "gte", "lte"] = "eq"
    value: str | int | float | bool


class MetricCreate(StrictSchema):
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$", max_length=80)
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    dataset: Dataset
    aggregation: Aggregation
    value_field: str | None = Field(default=None, max_length=80)
    unit: Literal["number", "currency", "percent", "hours", "days"] = "number"
    filters: list[SemanticFilter] = Field(default_factory=list, max_length=20)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def require_value_field(self) -> MetricCreate:
        if self.aggregation != "count" and not self.value_field:
            raise ValueError("A agregação escolhida exige um campo de valor.")
        return self


class MetricResponse(StrictSchema):
    id: UUID
    code: str
    name: str
    description: str | None
    dataset: str
    aggregation: str
    value_field: str | None
    unit: str
    filters: list[dict[str, object]]
    version: int
    active: bool
    created_at: datetime


class ReportCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    dataset: Dataset
    dimensions: list[str] = Field(default_factory=list, max_length=5)
    metric_codes: list[str] = Field(min_length=1, max_length=12)
    filters: list[SemanticFilter] = Field(default_factory=list, max_length=20)
    visualization: Literal["table", "bar", "line", "pie", "kpi"] = "table"

    @field_validator("dimensions", "metric_codes")
    @classmethod
    def unique_values(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Não repita campos ou métricas.")
        return value


class ReportResponse(StrictSchema):
    id: UUID
    name: str
    description: str | None
    dataset: str
    dimensions: list[str]
    metric_codes: list[str]
    filters: list[dict[str, object]]
    visualization: str
    status: str
    version: int
    created_at: datetime


class DashboardWidget(StrictSchema):
    report_id: UUID
    x: int = Field(ge=0, le=11)
    y: int = Field(ge=0, le=200)
    width: int = Field(ge=1, le=12)
    height: int = Field(ge=1, le=12)


class DashboardCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    layout: list[DashboardWidget] = Field(default_factory=list, max_length=30)


class DashboardResponse(StrictSchema):
    id: UUID
    name: str
    description: str | None
    layout: list[dict[str, object]]
    active: bool
    created_at: datetime


class ReportExecution(StrictSchema):
    report_id: UUID
    columns: list[str]
    rows: list[dict[str, object]]
    row_count: int
    duration_ms: int
