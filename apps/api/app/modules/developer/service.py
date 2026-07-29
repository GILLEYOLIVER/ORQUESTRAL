from __future__ import annotations

from app.modules.developer.schemas import PromotionEnvironment

PROMOTION_TARGETS: dict[PromotionEnvironment, frozenset[PromotionEnvironment]] = {
    "local": frozenset({"development", "testing"}),
    "development": frozenset({"testing", "staging"}),
    "testing": frozenset({"staging"}),
    "staging": frozenset({"production"}),
    "production": frozenset(),
}


def can_promote(source: PromotionEnvironment, target: PromotionEnvironment) -> bool:
    return target in PROMOTION_TARGETS[source]
