from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.schemas import StrictSchema

MemoryScope = Literal["conversation", "task", "user", "company", "operational"]
MemoryClassification = Literal["public", "internal", "confidential", "restricted"]
MemorySource = Literal["manual", "conversation", "task", "tool"]


class AgentMemoryPolicyUpdate(StrictSchema):
    default_retention_days: int = Field(default=30, ge=1, le=3650)
    max_retention_days: int = Field(default=365, ge=1, le=3650)
    allowed_scopes: list[MemoryScope] = Field(min_length=1, max_length=5)
    allowed_classifications: list[MemoryClassification] = Field(min_length=1, max_length=4)
    require_consent_for_user_scope: bool = True
    retrieval_enabled: bool = False
    max_retrieval_entries: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if self.default_retention_days > self.max_retention_days:
            raise ValueError("A retenção padrão não pode superar o limite máximo.")
        if len(set(self.allowed_scopes)) != len(self.allowed_scopes):
            raise ValueError("Os escopos não podem ser repetidos.")
        if len(set(self.allowed_classifications)) != len(self.allowed_classifications):
            raise ValueError("As classificações não podem ser repetidas.")
        return self


class AgentMemoryPolicyResponse(StrictSchema):
    id: UUID | None
    agent_id: UUID
    default_retention_days: int
    max_retention_days: int
    allowed_scopes: list[MemoryScope]
    allowed_classifications: list[MemoryClassification]
    require_consent_for_user_scope: bool
    retrieval_enabled: bool
    max_retrieval_entries: int
    updated_at: datetime | None


class AgentMemoryCreate(StrictSchema):
    content: str = Field(min_length=1, max_length=20_000)
    scope: MemoryScope
    classification: MemoryClassification = "internal"
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    source_type: MemorySource = "manual"
    source_id: str | None = Field(default=None, max_length=160)
    consent_reference: str | None = Field(default=None, max_length=160)

    @field_validator("content")
    @classmethod
    def trim_content(cls, value: str) -> str:
        return value.strip()


class AgentMemoryResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    scope: MemoryScope
    classification: MemoryClassification
    source_type: MemorySource
    source_id: str | None
    consent_reference: str | None
    expires_at: datetime
    expired: bool
    created_at: datetime


class AgentMemoryPurgeRequest(StrictSchema):
    expired_only: bool = True
    confirm_all: bool = False

    @model_validator(mode="after")
    def confirm_destructive_purge(self) -> Self:
        if not self.expired_only and not self.confirm_all:
            raise ValueError("Confirme explicitamente a eliminação de todas as memórias.")
        return self


class AgentMemoryPurgeResponse(StrictSchema):
    deleted_count: int
