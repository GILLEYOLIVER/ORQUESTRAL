from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.core.schemas import StrictSchema

DiscountType = Literal["percent", "fixed"]
PromotionTarget = Literal["all", "item", "variant"]


class ProductVariantCreate(StrictSchema):
    inventory_item_id: UUID
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=2, max_length=180)
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)


class ProductVariantResponse(StrictSchema):
    id: UUID
    inventory_item_id: UUID
    sku: str
    name: str
    attributes: dict[str, Any]
    active: bool
    created_at: datetime


class PromotionCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=180)
    code: str | None = Field(default=None, min_length=2, max_length=80)
    discount_type: DiscountType
    discount_value: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    applies_to: PromotionTarget = "all"
    inventory_item_id: UUID | None = None
    variant_id: UUID | None = None
    minimum_quantity: Decimal = Field(
        default=Decimal("1"), gt=0, max_digits=14, decimal_places=3
    )
    max_redemptions: int | None = Field(default=None, gt=0)
    starts_at: datetime
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> PromotionCreate:
        if self.discount_type == "percent" and self.discount_value > 100:
            raise ValueError("O desconto percentual não pode superar 100%.")
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("O encerramento deve ocorrer depois do início.")
        expected = {
            "all": self.inventory_item_id is None and self.variant_id is None,
            "item": self.inventory_item_id is not None and self.variant_id is None,
            "variant": self.variant_id is not None,
        }
        if not expected[self.applies_to]:
            raise ValueError("O alvo informado não corresponde ao tipo da promoção.")
        return self


class PromotionResponse(StrictSchema):
    id: UUID
    name: str
    code: str | None
    discount_type: DiscountType
    discount_value: Decimal
    applies_to: PromotionTarget
    inventory_item_id: UUID | None
    variant_id: UUID | None
    minimum_quantity: Decimal
    max_redemptions: int | None
    redeemed_count: int
    starts_at: datetime
    ends_at: datetime | None
    status: Literal["draft", "active", "paused", "expired"]
    created_at: datetime


class PriceResolutionRequest(StrictSchema):
    price_book_id: UUID
    inventory_item_id: UUID
    variant_id: UUID | None = None
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    promotion_code: str | None = Field(default=None, min_length=2, max_length=80)


class PriceResolutionResponse(StrictSchema):
    currency: str
    quantity: Decimal
    base_unit_price: Decimal
    discount_per_unit: Decimal
    final_unit_price: Decimal
    total: Decimal
    promotion_id: UUID | None
    promotion_name: str | None
    evidence: dict[str, Any]
