from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.core.schemas import StrictSchema

AgentProvider = Literal["local", "openai_compatible"]
AgentStatus = Literal["active", "inactive"]
ToolRunState = Literal["requested", "awaiting_confirmation", "approved", "rejected", "executing", "completed", "failed"]


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


class AgentToolDecision(StrictSchema):
    decision: Literal["approved", "rejected"]


class AgentUsageResponse(StrictSchema):
    id: UUID
    agent_id: UUID
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
