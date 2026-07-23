from __future__ import annotations

from decimal import Decimal

from app.modules.crm.sales_catalog_service import calculate_quote_line


def test_quote_line_calculation_is_decimal_and_deterministic() -> None:
    gross, discount, total = calculate_quote_line(
        Decimal("3"), Decimal("19.99"), Decimal("10")
    )
    assert gross == Decimal("59.97")
    assert discount == Decimal("6.00")
    assert total == Decimal("53.97")


def test_quote_line_supports_fractional_inventory_units() -> None:
    gross, discount, total = calculate_quote_line(
        Decimal("1.250"), Decimal("8.40"), Decimal("0")
    )
    assert (gross, discount, total) == (
        Decimal("10.50"),
        Decimal("0.00"),
        Decimal("10.50"),
    )
