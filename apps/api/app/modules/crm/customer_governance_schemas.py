from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerMatchRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=120)
    threshold: float = Field(default=0.88, ge=0.5, le=1)
    rules: dict[str, Any] = Field(
        default_factory=lambda: {
            "name_similarity_weight": 1.0,
            "exact_identity_weight": 1.0,
            "minimum_name_length": 4,
        }
    )


class CustomerMatchRuleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    version: int
    name: str
    status: Literal["draft", "published", "retired"]
    threshold: float
    rules: dict[str, Any]
    created_at: datetime
    published_at: datetime | None


class CustomerMatchScanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_version: int
    scanned_profiles: int
    candidates_created: int


class CustomerMergeCaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    primary_profile_id: UUID
    secondary_profile_id: UUID
    primary_name: str
    secondary_name: str
    status: Literal["pending", "approved", "rejected", "reverted"]
    score: float
    reasons: list[str]
    rule_version: int
    decision_note: str | None
    created_at: datetime
    reviewed_at: datetime | None
    reverted_at: datetime | None


class CustomerMergeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    note: str = Field(min_length=3, max_length=500)


class CustomerMergeRevert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=3, max_length=500)


class CustomerLineageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    observed_value: str = Field(min_length=1, max_length=2_000)
    source_id: UUID | None = None
    source_record_id: str | None = Field(default=None, max_length=160)
    classification: Literal["public", "internal", "confidential", "restricted"] = "internal"
    selected: bool = True


class CustomerLineageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    profile_id: UUID
    field_name: str
    value_fingerprint: str
    source_id: UUID | None
    source_record_id: str | None
    classification: str
    selected: bool
    observed_at: datetime
    recorded_by_user_id: UUID


class CustomerGovernanceEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    event_type: str
    subject_type: str
    subject_id: UUID
    actor_user_id: UUID
    payload: dict[str, Any]
    created_at: datetime
