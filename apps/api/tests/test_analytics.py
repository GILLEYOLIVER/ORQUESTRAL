from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.analytics.calculations import percentage_change, target_progress
from app.modules.analytics.schemas import MeasurementCreate


def test_analytics_calculates_change_and_goal_direction() -> None:
    assert percentage_change(Decimal("120"), Decimal("100")) == Decimal("20.00")
    assert target_progress(Decimal("120"), Decimal("100"), "higher_better") == (
        Decimal("120.00"),
        "achieved",
    )
    assert target_progress(Decimal("8"), Decimal("10"), "lower_better") == (
        Decimal("125.00"),
        "achieved",
    )


def test_analytics_rejects_invalid_measurement_period() -> None:
    with pytest.raises(ValidationError):
        MeasurementCreate(
            period_start=date(2026, 7, 20),
            period_end=date(2026, 7, 19),
            value=Decimal("10"),
        )
