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
    quarantine_minutes: int = Field(default=60, ge=5, le=1440)
    severity: Literal["low", "medium", "high", "critical"] = "high"
    required_review_quorum: int = Field(default=1, ge=1, le=5)
    review_sla_minutes: int = Field(default=60, ge=5, le=1440)
    responsible_user_ids: list[UUID] = Field(min_length=1, max_length=5)
    idempotency_key: UUID

    @field_validator("incident_reference", "reason")
    @classmethod
    def trim_incident_value(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_incident_quorum(self) -> Self:
        if self.severity == "critical" and self.required_review_quorum < 2:
            raise ValueError("Incidentes críticos exigem quorum mínimo de duas pessoas.")
        if len(set(self.responsible_user_ids)) != len(self.responsible_user_ids):
            raise ValueError("Cada responsável pode ser selecionado somente uma vez.")
        return self


class AgentTaskMemoryIncidentResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    revoked_grants: int
    quarantine_minutes: int
    quarantine_until: datetime
    quarantined: bool
    review_status: Literal["pending", "confirmed", "dismissed"]
    severity: Literal["low", "medium", "high", "critical"]
    required_review_quorum: int
    review_count: int
    review_sla_minutes: int
    review_due_at: datetime
    sla_breached: bool
    escalation_count: int
    escalated_at: datetime | None
    triggered_by_user_id: UUID
    responsible_user_ids: list[UUID]
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    already_processed: bool
    created_at: datetime


class AgentTaskMemoryIncidentReview(StrictSchema):
    decision: Literal["confirmed", "dismissed"]


class AgentTaskMemoryIncidentAssigneesUpdate(StrictSchema):
    responsible_user_ids: list[UUID] = Field(min_length=1, max_length=5)
    reason: str = Field(min_length=3, max_length=160)

    @field_validator("responsible_user_ids")
    @classmethod
    def validate_responsibles(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("Cada responsável pode ser selecionado somente uma vez.")
        return value

    @field_validator("reason")
    @classmethod
    def trim_assignment_reason(cls, value: str) -> str:
        return value.strip()


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
    pending_incident_reviews: int
    quarantined: bool
    quarantine_until: datetime | None
    overdue_incident_reviews: int


class AgentMemoryRiskReportPayload(StrictSchema):
    report_id: UUID
    agent_id: UUID
    generated_at: datetime
    sequence: int
    previous_signature: str | None
    signature_key_version: int
    risk_summary: AgentMemoryRiskSummary
    pending_incident_ids: list[UUID]


class AgentMemoryRiskReport(StrictSchema):
    payload: AgentMemoryRiskReportPayload
    signature_algorithm: Literal["HMAC-SHA256"] = "HMAC-SHA256"
    signature_key_id: Literal["orkestral-memory-risk-v1"] = "orkestral-memory-risk-v1"
    signature: str = Field(min_length=64, max_length=64)


class AgentMemoryRiskReportVerification(StrictSchema):
    valid: bool
    reason: str


class AgentMemoryResponseExerciseCreate(StrictSchema):
    scenario: Literal["full"] = "full"


class AgentMemoryResponseExerciseResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    scenario: Literal["full"]
    status: Literal["passed", "failed"]
    checks: dict[str, bool]
    source: Literal["manual", "manual_schedule", "worker_schedule"]
    duration_ms: int
    requested_by_user_id: UUID
    created_at: datetime


class AgentMemoryIncidentEscalationResponse(StrictSchema):
    escalated_count: int
    escalated_at: datetime


class AgentMemoryRiskSigningKeyResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    version: int
    activated_by_user_id: UUID
    created_at: datetime


class AgentMemoryExerciseScheduleUpdate(StrictSchema):
    enabled: bool
    cadence_hours: int = Field(default=168, ge=1, le=720)
    heartbeat_slo_minutes: int = Field(default=15, ge=5, le=1440)


class AgentMemoryExerciseScheduleResponse(StrictSchema):
    id: UUID | None
    agent_id: UUID
    enabled: bool
    cadence_hours: int
    heartbeat_slo_minutes: int
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_worker_heartbeat_at: datetime | None
    last_slo_alert_at: datetime | None
    slo_breach_count: int
    updated_at: datetime | None


class AgentMemoryExerciseDueResponse(StrictSchema):
    executed: bool
    next_run_at: datetime | None
    exercise: AgentMemoryResponseExerciseResponse | None


class AgentMemorySchedulerMetricsResponse(StrictSchema):
    agent_id: UUID
    worker_exercises: int
    worker_passed: int
    worker_failed: int
    average_duration_ms: float
    last_worker_run_at: datetime | None
    schedule_enabled: bool
    next_run_at: datetime | None
    overdue_seconds: int
    heartbeat_status: Literal["disabled", "waiting", "healthy", "overdue"]
    heartbeat_slo_minutes: int
    last_worker_heartbeat_at: datetime | None
    last_slo_alert_at: datetime | None
    slo_breach_count: int


class AgentMemoryReencryptionJobCreate(StrictSchema):
    batch_size: int = Field(default=100, ge=1, le=500)
    max_retry_attempts: int = Field(default=3, ge=1, le=10)
    key_credential_id: UUID | None = None


class AgentMemoryReencryptionJobRetry(StrictSchema):
    reason: str = Field(min_length=3, max_length=160)

    @field_validator("reason")
    @classmethod
    def trim_retry_reason(cls, value: str) -> str:
        return value.strip()


class AgentMemoryReencryptionJobClose(StrictSchema):
    closure_code: Literal["missing_key", "corrupted_material", "budget_exhausted", "other"]
    reason: str = Field(min_length=3, max_length=160)

    @field_validator("reason")
    @classmethod
    def trim_closure_reason(cls, value: str) -> str:
        return value.strip()


class AgentMemoryReencryptionJobResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    status: Literal["pending", "running", "completed", "failed", "closed"]
    target_master_key_id: str
    key_provider: Literal["environment", "external"]
    vault_credential_bound: bool
    batch_size: int
    total_count: int
    scanned_count: int
    rotated_count: int
    failed_count: int
    retry_count: int
    max_retry_attempts: int
    retry_attempts_remaining: int
    last_retry_at: datetime | None
    recovery_status: Literal["not_assessed", "ready", "blocked"]
    last_recovery_assessment_at: datetime | None
    recovery_assessed_by_user_id: UUID | None
    closure_code: str | None
    closed_at: datetime | None
    closed_by_user_id: UUID | None
    error_code: str | None
    requested_by_user_id: UUID
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    purge_after: datetime | None
    updated_at: datetime


class AgentMemoryReencryptionRecoveryAssessmentResponse(StrictSchema):
    job_id: UUID
    status: Literal["ready", "blocked"]
    checks: dict[str, bool]
    instructions: list[str]
    retry_attempts_remaining: int
    assessed_at: datetime


class AgentMemoryVaultCredentialOption(StrictSchema):
    id: UUID
    name: str
    plugin_code: str
    provider_name: str
    managed_provider: bool
    expires_at: datetime | None


class AgentMemoryKeyringStatusResponse(StrictSchema):
    source: Literal["environment", "managed"]
    provider_code: str
    status: Literal["active"]
    health_status: Literal["not_applicable", "unknown", "healthy", "unavailable"]
    activated_at: datetime | None
    last_resolved_at: datetime | None
    last_health_checked_at: datetime | None
    credential_expires_at: datetime | None
    expiry_warning_sent: bool
    automatic_exit_job_id: UUID | None
    automatic_exit_status: Literal["pending", "running", "completed", "failed", "closed"] | None
    slo_status: Literal["not_applicable", "within_slo", "breached"]


class AgentMemoryKeyringExitCreate(StrictSchema):
    batch_size: int = Field(default=100, ge=1, le=500)
    max_retry_attempts: int = Field(default=3, ge=1, le=10)


class AgentMemoryVaultIncidentResponse(StrictSchema):
    id: UUID
    provider_code: str
    status: Literal["open", "resolved"]
    failure_count: int
    alerted: bool
    slo_breached: bool
    first_detected_at: datetime
    last_detected_at: datetime
    resolved_at: datetime | None


class AgentMemoryKeyringPolicyUpdate(StrictSchema):
    expiry_warning_days: int = Field(ge=1, le=90)
    automatic_exit_enabled: bool = True
    automatic_exit_batch_size: int = Field(ge=1, le=500)
    vault_failure_alert_threshold: int = Field(ge=1, le=20)
    vault_slo_minutes: int = Field(ge=1, le=1440)


class AgentMemoryKeyringPolicyResponse(AgentMemoryKeyringPolicyUpdate):
    configured: bool
    updated_at: datetime | None


class AgentMemoryCredentialRenewalCreate(StrictSchema):
    extension_days: int = Field(ge=1, le=365)
    reason: str = Field(min_length=4, max_length=240)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        return value.strip()


class AgentMemoryCredentialRenewalResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    extension_days: int
    proposed_expires_at: datetime
    status: Literal["pending", "approved", "rejected"]
    requested_by_user_id: UUID
    decided_by_user_id: UUID | None
    created_at: datetime
    decided_at: datetime | None


class AgentMemoryReencryptionLegalHoldResponse(StrictSchema):
    id: UUID
    job_id: UUID
    reason_code: LegalHoldReason
    retention_days: int
    status: Literal["pending", "approved", "rejected", "expired"]
    requested_by_user_id: UUID
    decided_by_user_id: UUID | None
    expires_at: datetime
    expiration_reminder_sent: bool
    created_at: datetime
    decided_at: datetime | None


class AgentMemoryLegalHoldRenewalCreate(StrictSchema):
    extension_days: int = Field(ge=1, le=3650)
    legal_reference: str = Field(min_length=4, max_length=240)


class AgentMemoryLegalHoldRenewalResponse(StrictSchema):
    id: UUID
    hold_id: UUID
    job_id: UUID
    extension_days: int
    proposed_expires_at: datetime
    status: Literal["pending", "approved", "rejected"]
    requested_by_user_id: UUID
    decided_by_user_id: UUID | None
    created_at: datetime
    decided_at: datetime | None


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
