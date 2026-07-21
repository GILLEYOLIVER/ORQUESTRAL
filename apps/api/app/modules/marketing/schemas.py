from __future__ import annotations

from datetime import date, datetime
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
ExperimentStatus = Literal["draft", "running", "completed", "cancelled"]
ExperimentMetric = Literal["click_rate", "lead_rate", "conversion_rate", "revenue"]
AttributionTouchpoint = Literal[
    "first_touch", "lead_creation", "influenced", "last_touch", "conversion"
]


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


class CampaignMetricCreate(StrictSchema):
    observed_on: date
    channel: CampaignChannel = "multi_channel"
    variant_key: str = Field(default="all", min_length=1, max_length=80)
    impressions: int = Field(default=0, ge=0)
    reach: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    leads: int = Field(default=0, ge=0)
    conversions: int = Field(default=0, ge=0)
    spend_cents: int = Field(default=0, ge=0)
    revenue_cents: int = Field(default=0, ge=0)


class CampaignMetricResponse(StrictSchema):
    id: UUID
    campaign_id: UUID
    observed_on: date
    channel: CampaignChannel
    variant_key: str
    impressions: int
    reach: int
    clicks: int
    leads: int
    conversions: int
    spend_cents: int
    revenue_cents: int
    created_at: datetime
    updated_at: datetime


class CampaignPerformanceResponse(StrictSchema):
    campaign_id: UUID | None
    impressions: int
    reach: int
    clicks: int
    leads: int
    conversions: int
    spend_cents: int
    revenue_cents: int
    click_rate: float
    lead_rate: float
    conversion_rate: float
    cost_per_lead_cents: int
    acquisition_cost_cents: int
    roas: float


class ExperimentCreate(StrictSchema):
    campaign_id: UUID
    name: str = Field(min_length=2, max_length=180)
    hypothesis: str = Field(min_length=5, max_length=10_000)
    success_metric: ExperimentMetric
    variants: list[dict[str, Any]] = Field(min_length=2, max_length=10)


class ExperimentUpdate(StrictSchema):
    status: ExperimentStatus | None = None
    winner_key: str | None = Field(default=None, max_length=80)
    start_at: datetime | None = None
    end_at: datetime | None = None

    @model_validator(mode="after")
    def validate_experiment_update(self) -> ExperimentUpdate:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar.")
        return self


class ExperimentResponse(StrictSchema):
    id: UUID
    campaign_id: UUID
    name: str
    hypothesis: str
    success_metric: ExperimentMetric
    status: ExperimentStatus
    variants: list[dict[str, Any]]
    winner_key: str | None
    start_at: datetime | None
    end_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AttributionCreate(StrictSchema):
    contact_id: UUID | None = None
    opportunity_id: UUID | None = None
    touchpoint: AttributionTouchpoint
    source: str | None = Field(default=None, max_length=120)
    medium: str | None = Field(default=None, max_length=120)
    value_cents: int = Field(default=0, ge=0)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class AttributionResponse(StrictSchema):
    id: UUID
    campaign_id: UUID
    contact_id: UUID | None
    opportunity_id: UUID | None
    touchpoint: AttributionTouchpoint
    source: str | None
    medium: str | None
    value_cents: int
    metadata_json: dict[str, Any]
    occurred_at: datetime
    created_at: datetime
