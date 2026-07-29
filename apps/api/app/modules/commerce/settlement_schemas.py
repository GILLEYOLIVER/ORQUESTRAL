from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaymentIntentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["manual", "sandbox"] = "manual"
    method_type: str = Field(min_length=2, max_length=40)
    method_last4: str | None = Field(default=None, pattern=r"^\d{4}$")
    idempotency_key: str = Field(min_length=8, max_length=180)


class PaymentWebhook(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: UUID
    payment_intent_id: UUID
    provider_event_id: str = Field(min_length=3, max_length=180)
    event_type: Literal["captured", "failed", "cancelled", "refunded"]
    provider_reference: str | None = Field(default=None, max_length=180)


class PaymentIntentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    provider: str
    provider_reference: str
    method_type: str
    method_last4: str | None
    status: str
    amount: Decimal
    currency: str
    captured_at: datetime | None
    created_at: datetime


class ReturnLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_item_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class ReturnCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=5, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=180)
    items: list[ReturnLineCreate] = Field(min_length=1, max_length=100)

    @field_validator("items")
    @classmethod
    def unique_items(cls, value: list[ReturnLineCreate]) -> list[ReturnLineCreate]:
        identifiers = [item.order_item_id for item in value]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Cada item do pedido pode aparecer somente uma vez.")
        return value


class ReturnReceive(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_location_id: UUID
    resolution: Literal["credit", "refund"] = "credit"


class ReturnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    status: str
    reason: str
    resolution: str | None
    refund_amount: Decimal
    stock_location_id: UUID | None
    received_at: datetime | None
    created_at: datetime


class CommissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beneficiary_user_id: UUID
    rate: Decimal = Field(gt=0, le=100, max_digits=7, decimal_places=4)
    idempotency_key: str = Field(min_length=8, max_length=180)


class CommissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    beneficiary_user_id: UUID
    rate: Decimal
    amount: Decimal
    currency: str
    status: str
    financial_entry_id: UUID | None
    approved_at: datetime | None
    created_at: datetime


class SettlementOverview(BaseModel):
    payments: list[PaymentIntentResponse]
    returns: list[ReturnResponse]
    commissions: list[CommissionResponse]
