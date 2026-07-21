from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.schemas import StrictSchema

MemoryScope = Literal["conversation", "task", "user", "company", "operational"]
MemoryClassification = Literal["public", "internal", "confidential", "restricted"]
MemorySource = Literal["manual", "conversation", "task", "tool"]
MemoryPurpose = Literal["service", "personalization", "operations", "compliance", "analytics"]


class AgentMemoryScopePolicyInput(StrictSchema):
    scope: MemoryScope
    retention_days: int = Field(ge=1, le=3650)
    retrieval_enabled: bool = True


class AgentMemoryPurposePolicyInput(StrictSchema):
    purpose: MemoryPurpose
    retention_days: int = Field(ge=1, le=3650)
    enabled: bool = True


class AgentMemoryPolicyUpdate(StrictSchema):
    default_retention_days: int = Field(default=30, ge=1, le=3650)
    max_retention_days: int = Field(default=365, ge=1, le=3650)
    allowed_scopes: list[MemoryScope] = Field(min_length=1, max_length=5)
    allowed_classifications: list[MemoryClassification] = Field(min_length=1, max_length=4)
    require_consent_for_user_scope: bool = True
    retrieval_enabled: bool = False
    max_retrieval_entries: int = Field(default=5, ge=1, le=20)
    max_context_tokens: int = Field(default=1000, ge=128, le=16_000)
    max_shared_context_entries: int = Field(default=5, ge=1, le=20)
    max_shared_context_characters: int = Field(default=2000, ge=64, le=16_000)
    blocked_context_alert_threshold: int = Field(default=3, ge=2, le=20)
    scope_policies: list[AgentMemoryScopePolicyInput] = Field(default_factory=list, max_length=5)
    purpose_policies: list[AgentMemoryPurposePolicyInput] = Field(
        default_factory=list, max_length=5
    )

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if self.default_retention_days > self.max_retention_days:
            raise ValueError("A retenção padrão não pode superar o limite máximo.")
        if len(set(self.allowed_scopes)) != len(self.allowed_scopes):
            raise ValueError("Os escopos não podem ser repetidos.")
        if len(set(self.allowed_classifications)) != len(self.allowed_classifications):
            raise ValueError("As classificações não podem ser repetidas.")
        policy_scopes = [item.scope for item in self.scope_policies]
        if len(set(policy_scopes)) != len(policy_scopes):
            raise ValueError("Cada escopo pode possuir somente uma política.")
        if any(scope not in self.allowed_scopes for scope in policy_scopes):
            raise ValueError("Políticas por escopo exigem que o escopo esteja permitido.")
        if any(item.retention_days > self.max_retention_days for item in self.scope_policies):
            raise ValueError("A retenção do escopo supera o limite máximo da política.")
        purposes = [item.purpose for item in self.purpose_policies]
        if len(set(purposes)) != len(purposes):
            raise ValueError("Cada finalidade pode possuir somente uma política.")
        if any(item.retention_days > self.max_retention_days for item in self.purpose_policies):
            raise ValueError("A retenção da finalidade supera o limite máximo da política.")
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
    max_context_tokens: int
    max_shared_context_entries: int
    max_shared_context_characters: int
    blocked_context_alert_threshold: int
    scope_policies: list[AgentMemoryScopePolicyInput]
    purpose_policies: list[AgentMemoryPurposePolicyInput]
    updated_at: datetime | None


class AgentMemoryCreate(StrictSchema):
    content: str = Field(min_length=1, max_length=20_000)
    scope: MemoryScope
    classification: MemoryClassification = "internal"
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    source_type: MemorySource = "manual"
    source_id: str | None = Field(default=None, max_length=160)
    task_delegation_id: UUID | None = None
    purpose: MemoryPurpose = "operations"
    subject_user_id: UUID | None = None
    consent_reference: str | None = Field(default=None, max_length=160)

    @field_validator("content")
    @classmethod
    def trim_content(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_task_scope(self) -> Self:
        if self.scope == "task" and self.task_delegation_id is None:
            raise ValueError("Memórias de tarefa exigem uma delegação vinculada.")
        if self.scope != "task" and self.task_delegation_id is not None:
            raise ValueError("A delegação somente pode ser vinculada a memórias de tarefa.")
        if (
            self.task_delegation_id is not None
            and self.source_id is not None
            and self.source_id != str(self.task_delegation_id)
        ):
            raise ValueError("A origem informada não corresponde à delegação vinculada.")
        return self


class AgentMemoryResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    scope: MemoryScope
    classification: MemoryClassification
    source_type: MemorySource
    source_id: str | None
    task_delegation_id: UUID | None
    purpose: MemoryPurpose
    subject_user_id: UUID | None
    consent_recorded: bool
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


class AgentMemoryConsentRevoke(StrictSchema):
    subject_user_id: UUID
    consent_reference: str = Field(min_length=1, max_length=160)

    @field_validator("consent_reference")
    @classmethod
    def trim_consent_reference(cls, value: str) -> str:
        return value.strip()


class AgentMemoryConsentRevocationResponse(StrictSchema):
    revocation_id: UUID
    deleted_count: int
    already_revoked: bool


class AgentMemoryMetadataExport(StrictSchema):
    agent_id: UUID
    generated_at: datetime
    total: int
    memories: list[AgentMemoryResponse]


LegalHoldReason = Literal["legal_claim", "regulatory_request", "audit_preservation"]
LegalHoldStatus = Literal["pending", "approved", "rejected", "expired"]


class AgentMemoryLegalHoldCreate(StrictSchema):
    reason_code: LegalHoldReason
    legal_reference: str = Field(min_length=8, max_length=160)
    retention_days: int = Field(ge=1, le=3650)

    @field_validator("legal_reference")
    @classmethod
    def trim_legal_reference(cls, value: str) -> str:
        return value.strip()


class AgentMemoryLegalHoldDecision(StrictSchema):
    decision: Literal["approved", "rejected"]


class AgentMemoryLegalHoldResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    task_delegation_id: UUID
    reason_code: LegalHoldReason
    retention_days: int
    status: LegalHoldStatus
    requested_by_user_id: UUID
    decided_by_user_id: UUID | None
    expires_at: datetime
    created_at: datetime
    decided_at: datetime | None


TaskMemoryAccessPurpose = Literal["coordination", "review", "handoff"]
TaskMemoryAccessStatus = Literal["active", "revoked", "expired"]
TaskMemoryApprovalStatus = Literal["not_required", "pending", "approved", "rejected", "expired"]


def _default_shared_classifications() -> list[MemoryClassification]:
    return ["public", "internal"]


class AgentTaskMemoryAccessGrantCreate(StrictSchema):
    recipient_agent_id: UUID
    purpose: TaskMemoryAccessPurpose
    allowed_classifications: list[MemoryClassification] = Field(
        default_factory=_default_shared_classifications, min_length=1, max_length=4
    )
    allowed_tool_keys: list[str] = Field(min_length=1, max_length=50)
    max_classification: MemoryClassification = "internal"
    max_cost_microunits: int = Field(default=1000, ge=0, le=2_000_000_000)
    approval_expires_in_minutes: int = Field(default=30, ge=5, le=240)
    max_entries: int = Field(default=1, ge=1, le=5)
    max_content_characters: int = Field(default=512, ge=64, le=2000)
    expires_in_minutes: int = Field(default=60, ge=5, le=1440)
    idempotency_key: UUID

    @model_validator(mode="after")
    def validate_classifications(self) -> Self:
        if len(set(self.allowed_classifications)) != len(self.allowed_classifications):
            raise ValueError("As classificações compartilhadas não podem ser repetidas.")
        if len(set(self.allowed_tool_keys)) != len(self.allowed_tool_keys):
            raise ValueError("As ferramentas compartilhadas não podem ser repetidas.")
        if any(
            key != key.strip()
            or len(key) > 160
            or not all(character.isalnum() or character in "._-" for character in key)
            for key in self.allowed_tool_keys
        ):
            raise ValueError("Cada ferramenta deve possuir uma chave válida.")
        classification_rank = {
            "public": 0,
            "internal": 1,
            "confidential": 2,
            "restricted": 3,
        }
        if any(
            classification_rank[item] > classification_rank[self.max_classification]
            for item in self.allowed_classifications
        ):
            raise ValueError("A classificação compartilhada supera o teto do contrato.")
        return self


class AgentTaskMemoryAccessGrantResponse(StrictSchema):
    id: UUID
    task_delegation_id: UUID
    owner_agent_id: UUID
    recipient_agent_id: UUID
    purpose: TaskMemoryAccessPurpose
    allowed_classifications: list[MemoryClassification]
    allowed_tool_keys: list[str]
    max_classification: MemoryClassification
    max_cost_microunits: int
    requires_human_approval: bool
    approval_status: TaskMemoryApprovalStatus
    approval_ttl_minutes: int | None
    max_entries: int
    max_content_characters: int
    status: TaskMemoryAccessStatus
    granted_by_user_id: UUID
    approved_by_user_id: UUID | None
    revoked_by_user_id: UUID | None
    expires_at: datetime
    created_at: datetime
    approval_decided_at: datetime | None
    approval_expires_at: datetime | None
    revoked_at: datetime | None


class AgentTaskMemoryAccessRevoke(StrictSchema):
    reason: str = Field(min_length=3, max_length=160)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        return value.strip()


class AgentTaskMemoryAccessDecision(StrictSchema):
    decision: Literal["approved", "rejected"]


class AgentTaskMemoryIncidentRevoke(StrictSchema):
    incident_reference: str = Field(min_length=3, max_length=160)
    reason: str = Field(min_length=3, max_length=160)
    idempotency_key: UUID

    @field_validator("incident_reference", "reason")
    @classmethod
    def trim_incident_value(cls, value: str) -> str:
        return value.strip()


class AgentTaskMemoryIncidentResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    revoked_grants: int
    already_processed: bool
    created_at: datetime


class AgentMemoryRiskSummary(StrictSchema):
    agent_id: UUID
    generated_at: datetime
    risk_level: Literal["low", "elevated", "high", "critical"]
    active_grants: int
    restricted_active_grants: int
    pending_approvals: int
    expired_approvals: int
    blocked_events_last_24h: int
    cost_denials_last_24h: int
    incidents_last_30_days: int
    revoked_grants_last_30_days: int


class AgentTaskMemoryContextRequest(StrictSchema):
    grant_id: UUID
    purpose: TaskMemoryAccessPurpose


class AgentTaskMemoryContextItem(StrictSchema):
    memory_id: UUID
    owner_agent_id: UUID
    classification: MemoryClassification
    purpose: MemoryPurpose
    content: str
    truncated: bool
    created_at: datetime


class AgentTaskMemoryContextResponse(StrictSchema):
    grant_id: UUID
    task_delegation_id: UUID
    recipient_agent_id: UUID
    purpose: TaskMemoryAccessPurpose
    items: list[AgentTaskMemoryContextItem]
    total_characters: int
    blocked_items: int


TaskMemoryTraceOutcome = Literal[
    "consumed",
    "blocked",
    "empty",
    "revoked_before_use",
    "expired_before_use",
    "tool_policy_denied",
    "aggregate_limit_denied",
    "cost_limit_denied",
]


class AgentTaskMemoryAccessTraceResponse(StrictSchema):
    id: UUID
    grant_id: UUID
    task_delegation_id: UUID
    agent_run_id: UUID | None
    owner_agent_id: UUID
    recipient_agent_id: UUID
    outcome: TaskMemoryTraceOutcome
    item_count: int
    total_characters: int
    blocked_items: int
    estimated_cost_microunits: int
    created_at: datetime
