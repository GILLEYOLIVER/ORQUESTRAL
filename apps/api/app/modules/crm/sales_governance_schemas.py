from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.core.schemas import StrictSchema

GoalMetric = Literal["revenue", "won_opportunities", "new_accounts"]
GoalStatus = Literal["draft", "active", "completed", "cancelled"]
RenewalStatus = Literal["planned", "contacted", "negotiating", "renewed", "lost"]


class TerritoryCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    region_code: str | None = Field(default=None, max_length=40)
    owner_user_id: UUID | None = None


class TerritoryResponse(StrictSchema):
    id: UUID
    name: str
    description: str | None
    region_code: str | None
    owner_user_id: UUID | None
    status: Literal["active", "inactive"]
    open_opportunity_count: int
    created_at: datetime
    updated_at: datetime


class OpportunityTerritoryAssignment(StrictSchema):
    territory_id: UUID | None


class SalesGoalCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=180)
    metric: GoalMetric
    period_start: date
    period_end: date
    target_value: Decimal = Field(gt=0, decimal_places=2, max_digits=18)
    territory_id: UUID | None = None
    owner_user_id: UUID | None = None


class SalesGoalResponse(StrictSchema):
    id: UUID
    name: str
    metric: GoalMetric
    period_start: date
    period_end: date
    target_value: Decimal
    progress_value: Decimal
    progress_percent: Decimal
    territory_id: UUID | None
    territory_name: str | None
    owner_user_id: UUID | None
    status: GoalStatus
    created_at: datetime
    updated_at: datetime


class RenewalPlanCreate(StrictSchema):
    account_id: UUID
    source_opportunity_id: UUID | None = None
    owner_user_id: UUID | None = None
    title: str = Field(min_length=2, max_length=200)
    renewal_date: date
    expected_amount: Decimal = Field(ge=0, decimal_places=2, max_digits=16)


class RenewalStatusUpdate(StrictSchema):
    status: RenewalStatus
    note: str = Field(min_length=3, max_length=1000)


class RenewalPlanResponse(StrictSchema):
    id: UUID
    account_id: UUID
    account_name: str
    source_opportunity_id: UUID | None
    owner_user_id: UUID | None
    title: str
    renewal_date: date
    expected_amount: Decimal
    status: RenewalStatus
    last_note: str | None
    created_at: datetime
    updated_at: datetime


class SalesGovernanceDashboard(StrictSchema):
    generated_at: datetime
    active_territory_count: int
    active_goal_count: int
    open_renewal_count: int
    renewal_pipeline_amount: Decimal
    territories: list[TerritoryResponse]
    goals: list[SalesGoalResponse]
    renewals: list[RenewalPlanResponse]
