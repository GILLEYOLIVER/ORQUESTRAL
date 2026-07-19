from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.schemas import StrictSchema

BillingCycle = Literal["monthly", "yearly"]
PlanStatus = Literal["active", "inactive", "archived"]
SubscriptionStatus = Literal["trialing", "active"]
UsageMetric = Literal[
    "users",
    "agents",
    "workflows",
    "workflow_executions",
    "tokens",
    "storage_bytes",
    "integrations",
    "documents",
    "api_calls",
]

ALLOWED_LIMITS = frozenset(
    {
        "users",
        "agents",
        "workflows",
        "workflow_executions",
        "tokens",
        "storage_bytes",
        "integrations",
        "documents",
        "api_calls",
    }
)


def validate_limits(value: dict[str, int | None]) -> dict[str, int | None]:
    unknown = sorted(set(value) - ALLOWED_LIMITS)
    if unknown:
        raise ValueError(f"Limites desconhecidos: {', '.join(unknown)}")
    invalid = sorted(key for key, amount in value.items() if amount is not None and amount < 1)
    if invalid:
        raise ValueError(f"Limites devem ser positivos: {', '.join(invalid)}")
    return value


class PlanCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2_000)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    billing_cycle: BillingCycle
    limits: dict[str, int | None] = Field(default_factory=dict)
    status: PlanStatus = "active"

    _validate_limits = field_validator("limits")(validate_limits)


class PlanUpdate(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2_000)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    billing_cycle: BillingCycle | None = None
    limits: dict[str, int | None] | None = None
    status: PlanStatus | None = None

    @field_validator("limits")
    @classmethod
    def validate_optional_limits(
        cls, value: dict[str, int | None] | None
    ) -> dict[str, int | None] | None:
        return validate_limits(value) if value is not None else None


class PlanResponse(StrictSchema):
    id: UUID
    name: str
    description: str | None
    price: Decimal
    billing_cycle: BillingCycle
    limits: dict[str, int | None]
    status: PlanStatus
    created_at: datetime
    updated_at: datetime


class SubscriptionAssign(StrictSchema):
    plan_id: UUID
    status: SubscriptionStatus = "active"
    trial_ends_at: datetime | None = None

    @model_validator(mode="after")
    def validate_trial(self) -> SubscriptionAssign:
        if self.status == "trialing" and self.trial_ends_at is None:
            raise ValueError("trial_ends_at é obrigatório para uma assinatura em teste")
        return self


class SubscriptionResponse(StrictSchema):
    id: UUID
    company_id: UUID
    plan: PlanResponse
    status: str
    started_at: datetime
    trial_ends_at: datetime | None
    current_period_start: datetime
    current_period_end: datetime
    cancelled_at: datetime | None


class LimitResponse(StrictSchema):
    metric: UsageMetric
    label: str
    used: int
    limit: int | None
    remaining: int | None
    percentage: float | None
    exceeded: bool


class BillingOverviewResponse(StrictSchema):
    enforcement_enabled: bool
    subscription: SubscriptionResponse | None
    limits: list[LimitResponse]
    generated_at: datetime


class UsageRecordCreate(StrictSchema):
    metric: UsageMetric
    quantity: int = Field(ge=1)
    reference_date: date | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=180)


class UsageRecordResponse(StrictSchema):
    id: UUID
    company_id: UUID
    subscription_id: UUID | None
    metric: UsageMetric
    quantity: int
    reference_date: date
    metadata: dict[str, Any]
    idempotency_key: str | None
    created_at: datetime
