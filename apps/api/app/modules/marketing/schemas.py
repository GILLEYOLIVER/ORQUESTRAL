from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.core.schemas import StrictSchema

CampaignChannel = Literal["email", "whatsapp", "sms", "social", "multi_channel"]
CampaignStatus = Literal["draft", "scheduled", "active", "paused", "completed", "cancelled"]
AudienceStatus = Literal[
    "planned", "sent", "delivered", "engaged", "converted", "failed", "unsubscribed"
]
JourneyTrigger = Literal["manual", "contact_created", "contact_tagged", "scheduled"]
JourneyStatus = Literal["draft", "active", "paused", "archived"]
JourneyAction = Literal["wait", "email", "whatsapp", "task", "webhook"]


class CampaignCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=10_000)
    objective: str | None = Field(default=None, max_length=500)
    channel: CampaignChannel
    status: CampaignStatus = "draft"
    start_at: datetime | None = None
    end_at: datetime | None = None
    budget_cents: int = Field(default=0, ge=0, le=10_000_000_000)

    @model_validator(mode="after")
    def validate_campaign(self) -> CampaignCreate:
        self.name = self.name.strip()
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise ValueError("O encerramento deve ocorrer depois do inicio da campanha.")
        return self


class CampaignUpdate(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=10_000)
    objective: str | None = Field(default=None, max_length=500)
    channel: CampaignChannel | None = None
    status: CampaignStatus | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    budget_cents: int | None = Field(default=None, ge=0, le=10_000_000_000)
    spent_cents: int | None = Field(default=None, ge=0, le=10_000_000_000)


class CampaignResponse(StrictSchema):
    id: UUID
    name: str
    description: str | None
    objective: str | None
    channel: CampaignChannel
    status: CampaignStatus
    start_at: datetime | None
    end_at: datetime | None
    budget_cents: int
    spent_cents: int
    audience_total: int
    engaged_total: int
    converted_total: int
    created_at: datetime
    updated_at: datetime


class CampaignAudienceCreate(StrictSchema):
    contact_id: UUID
    scheduled_at: datetime | None = None


class CampaignAudienceUpdate(StrictSchema):
    status: AudienceStatus


class CampaignAudienceResponse(StrictSchema):
    id: UUID
    campaign_id: UUID
    contact_id: UUID
    status: AudienceStatus
    scheduled_at: datetime | None
    sent_at: datetime | None
    last_interaction_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MarketingSummaryResponse(StrictSchema):
    campaigns_total: int
    campaigns_active: int
    audience_total: int
    conversions_total: int


class JourneyCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=10_000)
    trigger_type: JourneyTrigger = "manual"
    status: JourneyStatus = "draft"


class JourneyUpdate(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=10_000)
    trigger_type: JourneyTrigger | None = None
    status: JourneyStatus | None = None


class JourneyResponse(StrictSchema):
    id: UUID
    name: str
    description: str | None
    trigger_type: JourneyTrigger
    status: JourneyStatus
    step_total: int
    created_at: datetime
    updated_at: datetime


class JourneyStepCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=180)
    action_type: JourneyAction
    position: int = Field(ge=0, le=10_000)
    configuration: dict[str, Any] = Field(default_factory=dict)


class JourneyStepUpdate(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    action_type: JourneyAction | None = None
    position: int | None = Field(default=None, ge=0, le=10_000)
    configuration: dict[str, Any] | None = None


class JourneyStepResponse(StrictSchema):
    id: UUID
    journey_id: UUID
    name: str
    action_type: JourneyAction
    position: int
    configuration: dict[str, Any]
    created_at: datetime
    updated_at: datetime
