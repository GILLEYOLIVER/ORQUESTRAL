from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.core.schemas import StrictSchema

AudienceKind = Literal["dynamic", "static"]
ReusableAudienceStatus = Literal["draft", "active", "paused", "archived"]


class MarketingAudienceCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=10_000)
    kind: AudienceKind
    segment_id: UUID | None = None

    @model_validator(mode="after")
    def validate_source(self) -> MarketingAudienceCreate:
        self.name = self.name.strip()
        if self.kind == "dynamic" and self.segment_id is None:
            raise ValueError("Selecione um segmento publicado para o público dinâmico.")
        if self.kind == "static" and self.segment_id is not None:
            raise ValueError("Públicos estáticos não utilizam segmento.")
        return self


class MarketingAudienceResponse(StrictSchema):
    id: UUID
    name: str
    description: str | None
    kind: AudienceKind
    status: ReusableAudienceStatus
    segment_id: UUID | None
    member_count: int
    synchronized_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MarketingAudienceMemberCreate(StrictSchema):
    contact_id: UUID


class MarketingAudienceMemberResponse(StrictSchema):
    id: UUID
    audience_id: UUID
    contact_id: UUID
    source: Literal["segment", "manual"]
    added_at: datetime


class MarketingAudienceSyncResponse(StrictSchema):
    audience_id: UUID
    member_count: int
    added_count: int
    removed_count: int
    excluded_restricted_count: int
    excluded_no_consent_count: int
    synchronized_at: datetime
