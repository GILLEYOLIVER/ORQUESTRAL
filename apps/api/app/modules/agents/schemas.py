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
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentConversationCloseResponse(StrictSchema):
    conversation: AgentConversationResponse
    deleted_memories: int


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


class AgentDataPolicyUpdate(StrictSchema):
    allowed_provider_keys: list[str] = Field(min_length=1, max_length=20)
    external_processing_enabled: bool = False
    allow_message_egress: bool = False
    allow_knowledge_egress: bool = False
    allow_memory_egress: bool = False
    redact_sensitive_data: bool = True
    require_evaluation_for_publish: bool = True
    max_data_classification: Literal["public", "internal", "confidential", "restricted"] = (
        "confidential"
    )

    @field_validator("allowed_provider_keys")
    @classmethod
    def normalize_providers(cls, values: list[str]) -> list[str]:
        normalized = sorted({value.strip().lower() for value in values if value.strip()})
        if not normalized:
            raise ValueError("Informe ao menos um provedor autorizado.")
        return normalized


class AgentDataPolicyResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    allowed_provider_keys: list[str]
    external_processing_enabled: bool
    allow_message_egress: bool
    allow_knowledge_egress: bool
    allow_memory_egress: bool
    redact_sensitive_data: bool
    require_evaluation_for_publish: bool
    max_data_classification: Literal["public", "internal", "confidential", "restricted"]
    created_at: datetime
    updated_at: datetime


class AgentSecurityEventResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    agent_run_id: UUID | None
    category: Literal["prompt_injection", "data_egress", "sensitive_data", "memory_access"]
    source: Literal["user", "knowledge", "memory", "provider", "system"]
    severity: Literal["low", "medium", "high", "critical"]
    action: Literal["blocked", "redacted", "reported"]
    content_fingerprint: str
    indicators: list[str]
    created_at: datetime


class AgentEvaluationCaseCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=160)
    input_text: str = Field(min_length=1, max_length=5000)
    expected_blocked: bool = False
    expected_tool_keys: list[str] = Field(default_factory=list, max_length=20)
    forbidden_tool_keys: list[str] = Field(default_factory=list, max_length=20)


class AgentEvaluationSuiteCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=160)
    minimum_score: int = Field(default=100, ge=0, le=100)
    cases: list[AgentEvaluationCaseCreate] = Field(min_length=1, max_length=100)


class AgentEvaluationCaseResponse(StrictSchema):
    id: UUID
    name: str
    input_text: str
    expected_blocked: bool
    expected_tool_keys: list[str]
    forbidden_tool_keys: list[str]


class AgentEvaluationSuiteResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    agent_version_id: UUID
    name: str
    minimum_score: int
    cases: list[AgentEvaluationCaseResponse]
    created_at: datetime


class AgentEvaluationRunResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    agent_version_id: UUID
    suite_id: UUID
    status: Literal["running", "passed", "failed"]
    total_cases: int
    passed_cases: int
    score: int
    started_at: datetime
    finished_at: datetime | None


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


class AgentRunStepResponse(StrictSchema):
    id: UUID
    agent_run_id: UUID
    sequence: int
    step_type: Literal["provider", "tool"]
    status: Literal[
        "planned",
        "completed",
        "blocked",
        "failed",
        "awaiting_approval",
        "simulated",
        "timed_out",
    ]
    summary_code: str
    tool_key: str | None
    input_fingerprint: str | None
    output_fingerprint: str | None
    error_code: str | None
    duration_ms: int
    started_at: datetime
    finished_at: datetime | None


class AgentTaskContractCreate(StrictSchema):
    worker_agent_id: UUID
    name: str = Field(min_length=2, max_length=160)
    allowed_tool_keys: list[str] = Field(default_factory=list, max_length=50)
    required_context_keys: list[str] = Field(default_factory=list, max_length=50)
    max_steps: int = Field(ge=1, le=100)
    max_cost_microunits: int = Field(ge=0, le=2_000_000_000)
    deadline_seconds: int = Field(default=300, ge=1, le=86_400)
    max_delegation_depth: int = Field(default=1, ge=1, le=5)


class AgentTaskContractResponse(StrictSchema):
    id: UUID
    supervisor_agent_id: UUID
    worker_agent_id: UUID
    name: str
    allowed_tool_keys: list[str]
    required_context_keys: list[str]
    max_steps: int
    max_cost_microunits: int
    deadline_seconds: int
    max_delegation_depth: int
    status: Literal["active", "inactive"]
    created_at: datetime


class AgentDelegationCreate(StrictSchema):
    contract_id: UUID
    objective: str = Field(min_length=2, max_length=5000)
    context_keys: list[str] = Field(default_factory=list, max_length=50)
    idempotency_key: UUID
    parent_delegation_id: UUID | None = None


class AgentDelegationTransition(StrictSchema):
    action: Literal["start", "complete", "fail", "cancel"]
    result: str | None = Field(default=None, max_length=5000)
    consumed_cost_microunits: int = Field(default=0, ge=0, le=2_000_000_000)


class AgentDelegationResponse(StrictSchema):
    id: UUID
    contract_id: UUID
    parent_delegation_id: UUID | None
    supervisor_agent_id: UUID
    assigned_agent_id: UUID
    idempotency_key: UUID
    objective_fingerprint: str
    result_fingerprint: str | None
    context_keys: list[str]
    status: Literal[
        "queued", "in_progress", "awaiting_approval", "completed", "failed", "cancelled"
    ]
    depth: int
    reserved_cost_microunits: int
    consumed_cost_microunits: int
    attempt_count: int
    claimed_by: str | None
    lease_expires_at: datetime | None
    last_error_code: str | None
    due_at: datetime
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AgentHandoffCreate(StrictSchema):
    to_agent_id: UUID
    reason_code: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9_.-]+$")


class AgentHandoffDecision(StrictSchema):
    decision: Literal["accepted", "rejected"]


class AgentHandoffResponse(StrictSchema):
    id: UUID
    delegation_id: UUID
    from_agent_id: UUID
    to_agent_id: UUID
    reason_code: str
    status: Literal["requested", "accepted", "rejected"]
    created_at: datetime
    decided_at: datetime | None


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
