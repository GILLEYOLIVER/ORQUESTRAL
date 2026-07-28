from __future__ import annotations

from datetime import datetime, time
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, model_validator

from app.core.schemas import StrictSchema

GovernedChannel = Literal["email", "whatsapp", "sms", "web"]
DeliveryStatus = Literal["reserved", "sent", "delivered", "failed", "blocked", "cancelled"]


class MarketingContactPolicyUpsert(StrictSchema):
    channel: GovernedChannel
    timezone: str = Field(default="America/Sao_Paulo", min_length=3, max_length=64)
    allowed_weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4], min_length=1, max_length=7)
    window_start: time = time(8)
    window_end: time = time(20)
    daily_limit: int = Field(default=2, ge=1, le=100)
    weekly_limit: int = Field(default=5, ge=1, le=500)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_policy(self) -> MarketingContactPolicyUpsert:
        self.allowed_weekdays = sorted(set(self.allowed_weekdays))
        if any(day < 0 or day > 6 for day in self.allowed_weekdays):
            raise ValueError("Dias permitidos devem estar entre 0 e 6.")
        if self.weekly_limit < self.daily_limit:
            raise ValueError("O limite semanal não pode ser menor que o diário.")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Fuso horário inválido.") from exc
        return self


class MarketingContactPolicyResponse(StrictSchema):
    id: UUID
    channel: GovernedChannel
    timezone: str
    allowed_weekdays: list[int]
    window_start: time
    window_end: time
    daily_limit: int
    weekly_limit: int
    enabled: bool
    updated_at: datetime


class MarketingDeliveryPreflightRequest(StrictSchema):
    contact_id: UUID
    channel: GovernedChannel
    idempotency_key: str = Field(min_length=8, max_length=120)
    campaign_id: UUID | None = None
    journey_id: UUID | None = None
    scheduled_for: datetime | None = None


class MarketingDeliveryDecision(StrictSchema):
    attempt_id: UUID
    allowed: bool
    status: DeliveryStatus
    reason_code: str
    scheduled_for: datetime
    daily_count: int
    weekly_count: int


class MarketingDeliveryOutcome(StrictSchema):
    status: Literal["sent", "delivered", "failed", "cancelled"]
    reason_code: str = Field(default="provider_result", min_length=2, max_length=64)
