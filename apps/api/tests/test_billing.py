from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.billing.schemas import PlanCreate, SubscriptionAssign
from app.modules.billing.service import (
    UsageMetric,
    assert_capacity,
    evaluate_limit,
    next_period_end,
)


def test_monthly_period_preserves_valid_day_at_month_end() -> None:
    start = datetime(2026, 1, 31, 12, tzinfo=UTC)
    assert next_period_end(start, "monthly") == datetime(2026, 2, 28, 12, tzinfo=UTC)


def test_yearly_period_handles_leap_day() -> None:
    start = datetime(2028, 2, 29, 9, tzinfo=UTC)
    assert next_period_end(start, "yearly") == datetime(2029, 2, 28, 9, tzinfo=UTC)


def test_limit_evaluation_blocks_projected_consumption() -> None:
    evaluation = evaluate_limit(UsageMetric.AGENTS, used=4, increment=2, configured_limit=5)
    assert evaluation.exceeded is True
    assert evaluation.remaining == 1
    with pytest.raises(HTTPException) as caught:
        assert_capacity(evaluation)
    assert caught.value.status_code == 402
    assert "limite de agentes" in str(caught.value.detail).lower()


def test_unconfigured_limit_is_unlimited() -> None:
    evaluation = evaluate_limit(
        UsageMetric.API_CALLS, used=1_000_000, increment=1, configured_limit=None
    )
    assert evaluation.exceeded is False
    assert evaluation.remaining is None
    assert evaluation.percentage is None


def test_plan_rejects_unknown_or_non_positive_limits() -> None:
    with pytest.raises(ValidationError):
        PlanCreate(
            name="Profissional",
            price=Decimal("199.90"),
            billing_cycle="monthly",
            limits={"unknown": 3},
        )
    with pytest.raises(ValidationError):
        PlanCreate(
            name="Profissional",
            price=Decimal("199.90"),
            billing_cycle="monthly",
            limits={"agents": 0},
        )


def test_trial_requires_end_date() -> None:
    with pytest.raises(ValidationError):
        SubscriptionAssign(
            plan_id="dbeea17f-80ee-43dd-9597-dfee1eac56be",
            status="trialing",
        )


def test_openapi_exposes_phase_12_routes(client: object) -> None:
    response = client.get("/openapi.json")  # type: ignore[attr-defined]
    paths = response.json()["paths"]
    assert "/billing/plans" in paths
    assert "/billing/overview" in paths
    assert "/billing/companies/{company_id}/subscription" in paths
