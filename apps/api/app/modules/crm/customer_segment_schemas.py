from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

ProfileType = Literal["person", "organization"]
LifecycleStatus = Literal["lead", "prospect", "customer", "inactive"]
ConsentPurpose = Literal[
    "marketing",
    "service",
    "analytics",
    "ai_processing",
    "data_sharing",
]
ConsentChannel = Literal["all", "email", "phone", "whatsapp", "sms", "web"]


class CustomerSegmentDefinition(BaseModel):
    profile_type: ProfileType | None = None
    lifecycle_status: LifecycleStatus | None = None
    min_quality_score: int = Field(default=0, ge=0, le=100)
    consent_purpose: ConsentPurpose | None = None
    consent_channel: ConsentChannel = "all"

    @model_validator(mode="after")
    def validate_consent(self) -> CustomerSegmentDefinition:
        if self.consent_purpose is None and self.consent_channel != "all":
            raise ValueError("Selecione uma finalidade para filtrar por canal.")
        return self


class CustomerSegmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1200)
    definition: CustomerSegmentDefinition


class CustomerSegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    status: Literal["draft", "published", "paused"]
    version: int
    definition: CustomerSegmentDefinition
    member_count: int
    materialized_at: datetime | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CustomerSegmentMaterializationResponse(BaseModel):
    segment_id: UUID
    member_count: int
    excluded_restricted_count: int
    materialized_at: datetime


class CustomerSegmentActivationRequest(BaseModel):
    campaign_id: UUID


class CustomerSegmentActivationResponse(BaseModel):
    id: UUID
    segment_id: UUID
    campaign_id: UUID
    status: Literal["completed", "partial", "blocked"]
    eligible_count: int
    activated_count: int
    excluded_restricted_count: int
    excluded_no_consent_count: int
    completed_at: datetime


class CustomerProfileSearchResult(BaseModel):
    profile_id: UUID
    display_name: str
    profile_type: str
    lifecycle_status: str
    quality_score: int
    identity_hint: str | None
    processing_restricted: bool


class CustomerProfileSearchResponse(BaseModel):
    query_kind: Literal["text", "email", "phone"]
    results: list[CustomerProfileSearchResult]
