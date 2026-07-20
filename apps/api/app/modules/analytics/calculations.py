from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

CalculatedTargetStatus = Literal["achieved", "behind", "no_target"]


def percentage_change(current: Decimal, previous: Decimal | None) -> Decimal | None:
    if previous is None or previous == 0:
        return None
    return ((current - previous) / abs(previous) * 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def target_progress(
    current: Decimal, target: Decimal | None, direction: str
) -> tuple[Decimal | None, CalculatedTargetStatus]:
    if target is None or direction == "neutral":
        return None, "no_target"
    achieved = current >= target if direction == "higher_better" else current <= target
    if direction == "higher_better":
        progress = Decimal("100") if target == 0 and achieved else Decimal("0")
        if target != 0:
            progress = current / target * 100
    else:
        progress = Decimal("100") if current == 0 else target / current * 100
    return (
        max(Decimal("0"), progress).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "achieved" if achieved else "behind",
    )
