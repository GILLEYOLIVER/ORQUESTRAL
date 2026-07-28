from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.core.schemas import StrictSchema


class JourneySimulationRequest(StrictSchema):
    sample_contact: dict[str, Any] = Field(default_factory=dict)


class JourneySimulationResponse(StrictSchema):
    id: UUID
    status: Literal["passed", "failed"]
    definition_checksum: str
    trace: list[dict[str, Any]]
    issues: list[dict[str, Any]]
    created_at: datetime


class JourneyVersionResponse(StrictSchema):
    id: UUID
    journey_id: UUID
    version: int
    status: Literal["published", "retired"]
    checksum: str
    definition: dict[str, Any]
    published_at: datetime


class ExperimentEvidenceCreate(StrictSchema):
    variant_key: str = Field(min_length=1, max_length=80)
    sample_size: int = Field(ge=0)
    metric_value: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    source_rule: str = Field(min_length=3, max_length=120)
    source_reference: str = Field(min_length=3, max_length=240)


class ExperimentEvidenceResponse(StrictSchema):
    id: UUID
    experiment_id: UUID
    variant_key: str
    sample_size: int
    metric_value: float
    confidence: float
    source_rule: str
    source_reference: str
    calculated_at: datetime


class MarketingAgentRecommendationCreate(StrictSchema):
    campaign_id: UUID
    agent_id: UUID


class MarketingAgentRecommendationDecision(StrictSchema):
    decision: Literal["approve", "dismiss"]


class MarketingAgentRecommendationResponse(StrictSchema):
    id: UUID
    campaign_id: UUID
    agent_id: UUID
    agent_version_id: UUID
    recommendation_type: str
    summary: str
    evidence: dict[str, Any]
    risk_level: Literal["low", "medium", "high"]
    status: Literal["proposed", "approved", "dismissed"]
    created_at: datetime
