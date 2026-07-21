from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.core.schemas import StrictSchema

AgentProvider = Literal["local", "openai_compatible"]
AgentStatus = Literal["active", "inactive"]
AgentVersionStatus = Literal["draft", "published", "retired"]
AgentRiskLevel = Literal["low", "medium", "high", "critical"]
AgentExecutionMode = Literal["live", "shadow", "simulation"]
ToolRunState = Literal[
    "requested", "awaiting_confirmation", "approved", "rejected", "executing", "completed", "failed"
]


class AgentCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    instructions: str = Field(min_length=10, max_length=20_000)
    provider: AgentProvider = "local"
    model: str = Field(default="orkestral-local", min_length=2, max_length=120)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_input_tokens: int = Field(default=4096, ge=256, le=200_000)
    max_output_tokens: int = Field(default=1024, ge=64, le=32_000)
    memory_enabled: bool = True

    @field_validator("name", "instructions")
    @classmethod
    def trim_required(cls, value: str) -> str:
        return value.strip()


class AgentUpdate(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    instructions: str | None = Field(default=None, min_length=10, max_length=20_000)
    provider: AgentProvider | None = None
    model: str | None = Field(default=None, min_length=2, max_length=120)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_input_tokens: int | None = Field(default=None, ge=256, le=200_000)
    max_output_tokens: int | None = Field(default=None, ge=64, le=32_000)
    memory_enabled: bool | None = None
    knowledge_base_id: UUID | None = None
    status: AgentStatus | None = None


class AgentResponse(StrictSchema):
    id: UUID
    name: str
    description: str | None
    instructions: str
    provider: AgentProvider
    model: str
    temperature: float
    max_input_tokens: int
    max_output_tokens: int
    memory_enabled: bool
    knowledge_base_id: UUID | None
    status: AgentStatus
    active_version_id: UUID | None
    created_at: datetime
    updated_at: datetime


class AgentToolCatalogResponse(StrictSchema):
    key: str
    name: str
    description: str
    input_schema: dict[str, Any]
    required_permission: str
    is_sensitive: bool


class AgentToolResponse(StrictSchema):
    id: UUID
    tool_key: str
    name: str
    description: str
    input_schema: dict[str, Any]
    required_permission: str | None
    risk_level: AgentRiskLevel
    is_sensitive: bool
    enabled: bool


class AgentToolsUpdate(StrictSchema):
    tool_keys: list[str] = Field(default_factory=list, max_length=50)


class AgentConversationCreate(StrictSchema):
    title: str | None = Field(default=None, max_length=180)


class AgentConversationResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    title: str
    status: Literal["open", "closed"]
    created_at: datetime
    updated_at: datetime


class AgentMessageResponse(StrictSchema):
    id: UUID
    conversation_id: UUID
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call: dict[str, Any]
    provider: str | None
    model: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_microunits: int
    duration_ms: int | None
    created_at: datetime


class AgentChatRequest(StrictSchema):
    message: str = Field(min_length=1, max_length=20_000)
    conversation_id: UUID | None = None
    execution_mode: AgentExecutionMode = "live"

    @field_validator("message")
    @classmethod
    def trim_message(cls, value: str) -> str:
        return value.strip()


class AgentToolRunResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    conversation_id: UUID | None
    tool_key: str
    tool_name: str
    state: ToolRunState
    requires_confirmation: bool
    result_summary: dict[str, Any]
    error_summary: str | None
    created_at: datetime
    updated_at: datetime


class AgentChatResponse(StrictSchema):
    conversation: AgentConversationResponse
    user_message: AgentMessageResponse
    assistant_message: AgentMessageResponse
    pending_actions: list[AgentToolRunResponse]
    run: AgentRunResponse


class AgentToolDecision(StrictSchema):
    decision: Literal["approved", "rejected"]


class AgentUsageResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    agent_version_id: UUID | None
    conversation_id: UUID | None
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_microunits: int
    tool_key: str | None
    duration_ms: int
    result_status: str
    created_at: datetime


class AgentProviderStatusResponse(StrictSchema):
    provider: AgentProvider
    configured: bool
    message: str


class AgentRunResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    agent_version_id: UUID
    conversation_id: UUID | None
    execution_mode: AgentExecutionMode
    status: Literal["running", "completed", "failed", "timed_out", "awaiting_approval", "simulated"]
    request_fingerprint: str
    planned_tool_keys: list[str]
    completed_tool_keys: list[str]
    denied_tool_keys: list[str]
    error_code: str | None
    step_count: int
    total_tokens: int
    cost_microunits: int
    duration_ms: int
    max_steps: int
    max_runtime_seconds: int
    started_at: datetime
    finished_at: datetime | None


class AgentVersionCreate(StrictSchema):
    instructions: str | None = Field(default=None, min_length=10, max_length=20_000)
    provider: AgentProvider | None = None
    model: str | None = Field(default=None, min_length=2, max_length=120)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_input_tokens: int | None = Field(default=None, ge=256, le=200_000)
    max_output_tokens: int | None = Field(default=None, ge=64, le=32_000)
    memory_enabled: bool | None = None
    knowledge_base_id: UUID | None = None
    autonomy_level: int | None = Field(default=None, ge=0, le=4)
    max_steps: int | None = Field(default=None, ge=1, le=100)
    max_runtime_seconds: int | None = Field(default=None, ge=1, le=3600)
    max_cost_per_run_microunits: int | None = Field(default=None, ge=0, le=2_000_000_000)


class AgentVersionResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    version: int
    status: AgentVersionStatus
    instructions: str
    provider: AgentProvider
    model: str
    temperature: float
    max_input_tokens: int
    max_output_tokens: int
    memory_enabled: bool
    knowledge_base_id: UUID | None
    autonomy_level: int
    max_steps: int
    max_runtime_seconds: int
    max_cost_per_run_microunits: int
    checksum: str
    created_at: datetime
    published_at: datetime | None


class AgentBudgetUpdate(StrictSchema):
    limit_microunits: int = Field(ge=0, le=2_000_000_000)
    hard_limit: bool = True


class AgentBudgetResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    currency: str
    limit_microunits: int
    reserved_microunits: int
    consumed_microunits: int
    hard_limit: bool
    cycle_started_at: datetime
    cycle_ends_at: datetime
    updated_at: datetime
