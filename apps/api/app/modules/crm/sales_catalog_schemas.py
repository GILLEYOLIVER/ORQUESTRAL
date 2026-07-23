from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.core.schemas import StrictSchema


class PriceBookCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=160)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    is_default: bool = False
    valid_from: date | None = None
    valid_until: date | None = None


class PriceBookEntryUpsert(StrictSchema):
    inventory_item_id: UUID
    unit_price: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    minimum_quantity: Decimal = Field(
        default=Decimal("1"), gt=0, max_digits=14, decimal_places=3
    )


class PriceBookEntryResponse(StrictSchema):
    id: UUID
    inventory_item_id: UUID
    sku: str
    item_name: str
    unit: str
    unit_price: Decimal
    minimum_quantity: Decimal
    active: bool


class PriceBookResponse(StrictSchema):
    id: UUID
    name: str
    currency: str
    status: Literal["draft", "published", "archived"]
    version: int
    is_default: bool
    valid_from: date | None
    valid_until: date | None
    published_at: datetime | None
    entries: list[PriceBookEntryResponse]
    created_at: datetime


class QuoteItemCreate(StrictSchema):
    inventory_item_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    discount_percent: Decimal = Field(
        default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2
    )


class QuoteCreate(StrictSchema):
    opportunity_id: UUID
    price_book_id: UUID
    title: str = Field(min_length=2, max_length=200)
    valid_until: date
    notes: str | None = Field(default=None, max_length=4_000)
    items: list[QuoteItemCreate] = Field(min_length=1, max_length=100)


class QuoteDecision(StrictSchema):
    decision: Literal["accepted", "rejected"]
    note: str = Field(min_length=3, max_length=1_000)


class QuoteItemResponse(StrictSchema):
    id: UUID
    inventory_item_id: UUID
    sku: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount_percent: Decimal
    line_total: Decimal


class QuoteResponse(StrictSchema):
    id: UUID
    opportunity_id: UUID
    account_id: UUID | None
    price_book_id: UUID
    quote_number: str
    title: str
    status: Literal["draft", "published", "accepted", "rejected", "expired"]
    version: int
    valid_until: date
    subtotal: Decimal
    discount_total: Decimal
    total: Decimal
    notes: str | None
    items: list[QuoteItemResponse]
    published_at: datetime | None
    decided_at: datetime | None
    created_at: datetime
