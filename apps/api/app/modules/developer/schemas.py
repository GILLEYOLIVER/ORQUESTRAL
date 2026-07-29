from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DeveloperEnvironment = Literal["development", "testing", "staging"]
PromotionEnvironment = Literal["local", "development", "testing", "staging", "production"]


class DeveloperSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class SandboxCreate(DeveloperSchema):
    code: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9-]+$")
    name: str = Field(min_length=2, max_length=120)
    environment: DeveloperEnvironment
    data_policy: Literal["empty", "synthetic", "masked"]
    expires_at: datetime


class SandboxResponse(SandboxCreate):
    id: UUID
    status: str
    created_by_user_id: UUID
    created_at: datetime
    archived_at: datetime | None


class PromotionCreate(DeveloperSchema):
    artifact_type: Literal["metadata", "automation", "agent", "plugin"]
    artifact_ref: str = Field(min_length=1, max_length=200)
    source_environment: PromotionEnvironment
    target_environment: PromotionEnvironment
    checksum: str = Field(pattern=r"^[a-f0-9]{64}$")


class PromotionDecision(DeveloperSchema):
    decision: Literal["approved", "rejected"]


class PromotionResponse(PromotionCreate):
    id: UUID
    status: str
    requested_by_user_id: UUID
    reviewed_by_user_id: UUID | None
    requested_at: datetime
    reviewed_at: datetime | None
