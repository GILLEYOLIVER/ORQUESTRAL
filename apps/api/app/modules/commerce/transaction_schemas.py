from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.core.schemas import StrictSchema


class OrderFromQuoteCreate(StrictSchema):
    quote_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=180)


class OrderReserve(StrictSchema):
    location_id: UUID


class OrderConfirm(StrictSchema):
    due_date: date
    account_id: UUID | None = None
    category_id: UUID | None = None
    create_contract: bool = False
    contract_ends_on: date | None = None
    billing_interval: Literal["monthly", "yearly"] | None = None
    terms: str | None = Field(default=None, max_length=10_000)

    @model_validator(mode="after")
    def validate_contract(self) -> OrderConfirm:
        today = date.today()
        if self.due_date < today:
            raise ValueError("O vencimento financeiro não pode estar no passado.")
        if self.billing_interval is not None and not self.create_contract:
            raise ValueError("Assinatura comercial exige contrato.")
        if self.contract_ends_on is not None and self.contract_ends_on < today:
            raise ValueError("O contrato não pode terminar no passado.")
        return self


class OrderItemResponse(StrictSchema):
    id: UUID
    inventory_item_id: UUID
    sku: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount_total: Decimal
    line_total: Decimal


class OrderResponse(StrictSchema):
    id: UUID
    quote_id: UUID
    account_id: UUID | None
    financial_entry_id: UUID | None
    order_number: str
    currency: str
    status: Literal["draft", "reserved", "confirmed", "fulfilled", "cancelled"]
    subtotal: Decimal
    discount_total: Decimal
    total: Decimal
    items: list[OrderItemResponse]
    confirmed_at: datetime | None
    created_at: datetime


class ContractResponse(StrictSchema):
    id: UUID
    order_id: UUID
    contract_number: str
    title: str
    status: str
    starts_on: date
    ends_on: date | None
    total_value: Decimal
    billing_interval: str | None
    next_billing_on: date | None
