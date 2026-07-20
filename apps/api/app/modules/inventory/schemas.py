from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.core.schemas import StrictSchema

InventoryUnit = Literal["unit", "kg", "g", "l", "ml", "m", "box"]
MovementType = Literal["in", "out", "adjustment"]


class CategoryCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class CategoryResponse(StrictSchema):
    id: UUID
    name: str
    description: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


class LocationCreate(StrictSchema):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=2, max_length=140)
    description: str | None = Field(default=None, max_length=500)


class LocationUpdate(StrictSchema):
    code: str | None = Field(default=None, min_length=1, max_length=40)
    name: str | None = Field(default=None, min_length=2, max_length=140)
    description: str | None = Field(default=None, max_length=500)
    active: bool | None = None


class LocationResponse(StrictSchema):
    id: UUID
    code: str
    name: str
    description: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


class ItemCreate(StrictSchema):
    sku: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=10_000)
    category_id: UUID | None = None
    unit: InventoryUnit = "unit"
    minimum_stock: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)


class ItemUpdate(StrictSchema):
    sku: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=10_000)
    category_id: UUID | None = None
    unit: InventoryUnit | None = None
    minimum_stock: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    active: bool | None = None


class ItemResponse(StrictSchema):
    id: UUID
    sku: str
    name: str
    description: str | None
    category_id: UUID | None
    unit: InventoryUnit
    minimum_stock: Decimal
    total_quantity: Decimal
    low_stock: bool
    active: bool
    created_at: datetime
    updated_at: datetime


class BalanceResponse(StrictSchema):
    id: UUID
    item_id: UUID
    location_id: UUID
    quantity: Decimal
    updated_at: datetime


class MovementCreate(StrictSchema):
    item_id: UUID
    location_id: UUID
    movement_type: MovementType
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=3)
    adjusted_quantity: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    reason: str = Field(min_length=2, max_length=300)
    reference: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_quantity(self) -> MovementCreate:
        if self.movement_type == "adjustment" and self.adjusted_quantity is None:
            raise ValueError("Informe o saldo contado para realizar um ajuste.")
        if self.movement_type != "adjustment" and self.quantity is None:
            raise ValueError("Informe a quantidade da movimentacao.")
        return self


class MovementResponse(StrictSchema):
    id: UUID
    item_id: UUID
    location_id: UUID
    movement_type: MovementType
    quantity: Decimal
    previous_quantity: Decimal
    resulting_quantity: Decimal
    reason: str
    reference: str | None
    occurred_at: datetime
    created_at: datetime


class InventorySummaryResponse(StrictSchema):
    items_total: int
    locations_total: int
    low_stock_total: int
    total_quantity: Decimal
