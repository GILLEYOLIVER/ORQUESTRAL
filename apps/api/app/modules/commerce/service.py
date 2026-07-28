from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

MONEY = Decimal("0.01")


def calculate_discount(
    base_price: Decimal, discount_type: str, discount_value: Decimal
) -> Decimal:
    if discount_type == "percent":
        discount = base_price * discount_value / Decimal("100")
    else:
        discount = discount_value
    return min(base_price, discount).quantize(MONEY, rounding=ROUND_HALF_UP)
