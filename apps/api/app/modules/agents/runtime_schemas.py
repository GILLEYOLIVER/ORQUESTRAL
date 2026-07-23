from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.schemas import StrictSchema


class RequiredToolsMixin(StrictSchema):
    required_tool_keys: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("required_tool_keys")
    @classmethod
    def normalize_tools(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().lower() for item in value if item.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Cada ferramenta só pode ser informada uma vez.")
        if any(len(item) > 160 for item in normalized):
            raise ValueError("Identificador de ferramenta muito longo.")
        return normalized


class AgentScheduleCreate(RequiredToolsMixin):
    schedule_key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=2, max_length=160)
    objective: str = Field(min_length=5, max_length=1000)
    cadence_minutes: int = Field(ge=5, le=10_080)
    first_run_at: datetime | None = None


class AgentScheduleResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    agent_version_id: UUID
    schedule_key: str
    version: int
    status: Literal["draft", "published", "paused", "retired"]
    name: str
    objective: str
    cadence_minutes: int
    required_tool_keys: list[str]
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    published_at: datetime | None


class AgentTriggerCreate(RequiredToolsMixin):
    trigger_key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=2, max_length=160)
    event_type: str = Field(min_length=3, max_length=160, pattern=r"^[a-z][a-z0-9_.-]+$")
    min_event_version: int = Field(default=1, ge=1, le=1000)
    max_event_version: int | None = Field(default=None, ge=1, le=1000)
    objective: str = Field(min_length=5, max_length=1000)

    @model_validator(mode="after")
    def validate_version_range(self) -> Self:
        if self.max_event_version is not None and self.max_event_version < self.min_event_version:
            raise ValueError("A versão máxima não pode ser menor que a mínima.")
        return self


class AgentTriggerResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    agent_version_id: UUID
    trigger_key: str
    version: int
    status: Literal["draft", "published", "paused", "retired"]
    name: str
    event_type: str
    min_event_version: int
    max_event_version: int | None
    objective: str
    required_tool_keys: list[str]
    created_at: datetime
    published_at: datetime | None


class AgentCredentialCatalogResponse(StrictSchema):
    id: UUID
    plugin_id: UUID
    name: str
    status: Literal["active", "expired", "revoked"]
    expires_at: datetime | None
    usable: bool


class AgentCredentialBindingCreate(StrictSchema):
    credential_id: UUID
    enabled: bool = True


class AgentCredentialBindingResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    tool_key: str
    credential_id: UUID
    enabled: bool
    created_at: datetime
    updated_at: datetime


class AgentRuntimeDispatchResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    agent_version_id: UUID
    schedule_id: UUID | None
    trigger_id: UUID | None
    source_event_id: UUID | None
    source_type: Literal["schedule", "event"]
    status: Literal["ready", "blocked"]
    reason_code: str | None
    required_tool_keys: list[str]
    scheduled_for: datetime
    created_at: datetime
