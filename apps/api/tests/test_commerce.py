from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.commerce.schemas import PromotionCreate
from app.modules.commerce.service import calculate_discount
from app.modules.commerce.transaction_schemas import OrderConfirm
from app.modules.commerce.transaction_service import next_period


def test_discount_is_deterministic_and_never_negative() -> None:
    assert calculate_discount(Decimal("100"), "percent", Decimal("15")) == Decimal("15.00")
    assert calculate_discount(Decimal("20"), "fixed", Decimal("50")) == Decimal("20.00")


def test_promotion_rejects_invalid_target_and_window() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        PromotionCreate(
            name="Inválida",
            discount_type="percent",
            discount_value=Decimal("10"),
            applies_to="item",
            starts_at=now,
            ends_at=now - timedelta(days=1),
        )


def test_customer_subscription_period_handles_month_end() -> None:
    assert next_period(datetime(2026, 1, 31, tzinfo=UTC).date(), "monthly").isoformat() == "2026-02-28"
    assert next_period(datetime(2024, 2, 29, tzinfo=UTC).date(), "yearly").isoformat() == "2025-02-28"


def test_subscription_requires_commercial_contract() -> None:
    with pytest.raises(ValidationError):
        OrderConfirm(
            due_date=datetime.now(UTC).date(),
            create_contract=False,
            billing_interval="monthly",
        )


def test_order_rejects_past_due_date() -> None:
    with pytest.raises(ValidationError):
        OrderConfirm(due_date=datetime.now(UTC).date() - timedelta(days=1))
