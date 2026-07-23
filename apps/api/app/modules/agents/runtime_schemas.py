from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.schemas import StrictSchema


class RequiredToolsMixin(StrictSchema):
    required_tool_keys: list[str] = Field(default_factory=list, max_length=20)
    tool_arguments: dict[str, dict[str, Any]] = Field(default_factory=dict, max_length=20)
    execution_mode: Literal["shadow", "live"] = "shadow"
    canary_percentage: int = Field(default=0, ge=0, le=100)

    @field_validator("required_tool_keys")
    @classmethod
    def normalize_tools(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().lower() for item in value if item.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Cada ferramenta só pode ser informada uma vez.")
        if any(len(item) > 160 for item in normalized):
            raise ValueError("Identificador de ferramenta muito longo.")
        return normalized

    @model_validator(mode="after")
    def validate_tool_arguments(self) -> Self:
        normalized = {key.strip().lower(): value for key, value in self.tool_arguments.items()}
        unknown = sorted(set(normalized) - set(self.required_tool_keys))
        if unknown:
            raise ValueError("Existem argumentos para ferramentas não selecionadas.")
        self.tool_arguments = normalized
        return self


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
    tool_arguments: dict[str, dict[str, Any]]
    execution_mode: Literal["shadow", "live"]
    canary_percentage: int
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
    tool_arguments: dict[str, dict[str, Any]]
    execution_mode: Literal["shadow", "live"]
    canary_percentage: int
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
    source_type: Literal["schedule", "event", "retry"]
    retry_of_dispatch_id: UUID | None
    status: Literal[
        "ready",
        "blocked",
        "processing",
        "awaiting_approval",
        "simulated",
        "completed",
        "failed",
    ]
    reason_code: str | None
    error_code: str | None
    required_tool_keys: list[str]
    tool_arguments: dict[str, dict[str, Any]]
    execution_mode: Literal["shadow", "live"]
    canary_percentage: int
    agent_run_id: UUID | None
    attempt_count: int
    scheduled_for: datetime
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class AgentDispatchReviewCreate(StrictSchema):
    decision: Literal["close", "retry"]
    reason: str = Field(min_length=10, max_length=1000)
    idempotency_key: UUID


class AgentDispatchRetryApproval(StrictSchema):
    idempotency_key: UUID


class AgentDispatchReviewResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    interrupted_dispatch_id: UUID
    replacement_dispatch_id: UUID | None
    decision: Literal["close", "retry"]
    status: Literal["closed", "pending_approval", "approved"]
    reason: str
    requested_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime
