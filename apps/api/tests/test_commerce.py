from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.commerce.schemas import PromotionCreate
from app.modules.commerce.service import calculate_discount


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
