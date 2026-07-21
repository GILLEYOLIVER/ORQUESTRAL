from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentMemoryPolicy(Base):
    __tablename__ = "agent_memory_policies"
    __table_args__ = (
        UniqueConstraint("agent_id", name="uq_agent_memory_policies_agent"),
        CheckConstraint(
            "default_retention_days BETWEEN 1 AND 3650",
            name="ck_agent_memory_policy_default_retention",
        ),
        CheckConstraint(
            "max_retention_days BETWEEN default_retention_days AND 3650",
            name="ck_agent_memory_policy_max_retention",
        ),
        CheckConstraint(
            "max_retrieval_entries BETWEEN 1 AND 20",
            name="ck_agent_memory_policy_retrieval_limit",
        ),
        CheckConstraint(
            "max_context_tokens BETWEEN 128 AND 16000",
            name="ck_agent_memory_policy_context_tokens",
        ),
        CheckConstraint(
            "max_shared_context_entries BETWEEN 1 AND 20",
            name="ck_agent_memory_policy_shared_entries",
        ),
        CheckConstraint(
            "max_shared_context_characters BETWEEN 64 AND 16000",
            name="ck_agent_memory_policy_shared_characters",
        ),
        CheckConstraint(
            "blocked_context_alert_threshold BETWEEN 2 AND 20",
            name="ck_agent_memory_policy_blocked_alert",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    default_retention_days: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    max_retention_days: Mapped[int] = mapped_column(Integer, default=365, server_default="365")
    allowed_scopes: Mapped[list[str]] = mapped_column(
        JSONB,
        default=lambda: ["conversation", "task", "operational"],
        server_default=text('\'["conversation","task","operational"]\'::jsonb'),
    )
    allowed_classifications: Mapped[list[str]] = mapped_column(
        JSONB,
        default=lambda: ["public", "internal"],
        server_default=text('\'["public","internal"]\'::jsonb'),
    )
    require_consent_for_user_scope: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    retrieval_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    max_retrieval_entries: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    max_context_tokens: Mapped[int] = mapped_column(Integer, default=1000, server_default="1000")
    max_shared_context_entries: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    max_shared_context_characters: Mapped[int] = mapped_column(
        Integer, default=2000, server_default="2000"
    )
    blocked_context_alert_threshold: Mapped[int] = mapped_column(
        Integer, default=3, server_default="3"
    )
    updated_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class AgentMemoryScopePolicy(Base):
    __tablename__ = "agent_memory_scope_policies"
    __table_args__ = (
        UniqueConstraint("agent_id", "scope", name="uq_agent_memory_scope_policy"),
        CheckConstraint(
            "scope IN ('conversation', 'task', 'user', 'company', 'operational')",
            name="ck_agent_memory_scope_policy_scope",
        ),
        CheckConstraint(
            "retention_days BETWEEN 1 AND 3650",
            name="ck_agent_memory_scope_policy_retention",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(String(24), index=True)
    retention_days: Mapped[int] = mapped_column(Integer)
    retrieval_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class AgentMemoryPurposePolicy(Base):
    __tablename__ = "agent_memory_purpose_policies"
    __table_args__ = (
        UniqueConstraint("agent_id", "purpose", name="uq_agent_memory_purpose_policy"),
        CheckConstraint(
            "purpose IN ('service', 'personalization', 'operations', 'compliance', 'analytics')",
            name="ck_agent_memory_purpose_policy_purpose",
        ),
        CheckConstraint(
            "retention_days BETWEEN 1 AND 3650",
            name="ck_agent_memory_purpose_policy_retention",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(24), index=True)
    retention_days: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class AgentMemoryEntry(Base):
    __tablename__ = "agent_memory_entries"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "agent_id", "content_fingerprint", name="uq_agent_memory_content"
        ),
        CheckConstraint(
            "scope IN ('conversation', 'task', 'user', 'company', 'operational')",
            name="ck_agent_memory_scope",
        ),
        CheckConstraint(
            "classification IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_agent_memory_classification",
        ),
        CheckConstraint(
            "source_type IN ('manual', 'conversation', 'task', 'tool')",
            name="ck_agent_memory_source_type",
        ),
        CheckConstraint(
            "purpose IN ('service', 'personalization', 'operations', 'compliance', 'analytics')",
            name="ck_agent_memory_purpose",
        ),
        CheckConstraint("expires_at > created_at", name="ck_agent_memory_expiration"),
        CheckConstraint(
            "scope <> 'user' OR (subject_user_id IS NOT NULL AND subject_membership_id IS NOT NULL)",
            name="ck_agent_memory_user_subject",
        ),
        CheckConstraint(
            "scope = 'user' OR (subject_user_id IS NULL AND subject_membership_id IS NULL AND consent_fingerprint IS NULL)",
            name="ck_agent_memory_non_user_subject",
        ),
        CheckConstraint(
            "scope <> 'task' OR task_delegation_id IS NOT NULL",
            name="ck_agent_memory_task_delegation_required",
        ),
        CheckConstraint(
            "scope = 'task' OR task_delegation_id IS NULL",
            name="ck_agent_memory_task_delegation_scope",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    scope: Mapped[str] = mapped_column(String(24), index=True)
    classification: Mapped[str] = mapped_column(String(24), index=True)
    encrypted_content: Mapped[bytes] = mapped_column(LargeBinary)
    content_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    source_type: Mapped[str] = mapped_column(String(24), default="manual", server_default="manual")
    source_id: Mapped[str | None] = mapped_column(String(160))
    task_delegation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_delegations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    purpose: Mapped[str] = mapped_column(
        String(24), default="operations", server_default="operations", index=True
    )
    subject_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    subject_membership_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("company_users.id", ondelete="CASCADE"), index=True
    )
    consent_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )


class AgentMemoryLegalHold(Base):
    __tablename__ = "agent_memory_legal_holds"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_agent_memory_legal_hold_status",
        ),
        CheckConstraint(
            "reason_code IN ('legal_claim', 'regulatory_request', 'audit_preservation')",
            name="ck_agent_memory_legal_hold_reason",
        ),
        CheckConstraint(
            "retention_days BETWEEN 1 AND 3650",
            name="ck_agent_memory_legal_hold_retention",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="ck_agent_memory_legal_hold_expiration",
        ),
        CheckConstraint(
            "decided_by_user_id IS NULL OR decided_by_user_id <> requested_by_user_id",
            name="ck_agent_memory_legal_hold_separation",
        ),
        CheckConstraint(
            "(status = 'pending' AND decided_by_user_id IS NULL AND decided_at IS NULL) OR "
            "(status IN ('approved', 'rejected') AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL)",
            name="ck_agent_memory_legal_hold_decision",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    task_delegation_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_delegations.id", ondelete="CASCADE"), index=True
    )
    reason_code: Mapped[str] = mapped_column(String(32), index=True)
    legal_reference_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    retention_days: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", index=True
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    decided_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentTaskMemoryAccessIncident(Base):
    __tablename__ = "agent_task_memory_access_incidents"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "idempotency_key",
            name="uq_agent_task_memory_incident_idempotency",
        ),
        CheckConstraint(
            "revoked_grants >= 0",
            name="ck_agent_task_memory_incident_revoked_grants",
        ),
        CheckConstraint(
            "quarantine_minutes BETWEEN 5 AND 1440 AND quarantine_until >= created_at",
            name="ck_agent_task_memory_incident_quarantine",
        ),
        CheckConstraint(
            "review_status IN ('pending', 'confirmed', 'dismissed')",
            name="ck_agent_task_memory_incident_review_status",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_agent_task_memory_incident_severity",
        ),
        CheckConstraint(
            "required_review_quorum BETWEEN 1 AND 5 "
            "AND (severity <> 'critical' OR required_review_quorum >= 2) "
            "AND review_count >= 0",
            name="ck_agent_task_memory_incident_quorum",
        ),
        CheckConstraint(
            "review_sla_minutes BETWEEN 5 AND 1440 AND review_due_at > created_at "
            "AND escalation_count >= 0",
            name="ck_agent_task_memory_incident_sla",
        ),
        CheckConstraint(
            "(review_status = 'pending' AND reviewed_by_user_id IS NULL "
            "AND reviewed_at IS NULL) OR "
            "(review_status IN ('confirmed', 'dismissed') AND reviewed_by_user_id IS NOT NULL "
            "AND reviewed_at IS NOT NULL AND reviewed_by_user_id <> triggered_by_user_id)",
            name="ck_agent_task_memory_incident_review",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    owner_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    idempotency_key: Mapped[UUID] = mapped_column(index=True)
    incident_reference_fingerprint: Mapped[str] = mapped_column(String(64))
    reason_fingerprint: Mapped[str] = mapped_column(String(64))
    revoked_grants: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    quarantine_minutes: Mapped[int] = mapped_column(Integer, default=60, server_default="60")
    quarantine_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    review_status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", index=True
    )
    severity: Mapped[str] = mapped_column(String(16), default="high", server_default="high")
    required_review_quorum: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    review_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    review_sla_minutes: Mapped[int] = mapped_column(Integer, default=60, server_default="60")
    review_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    escalation_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    triggered_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AgentTaskMemoryIncidentReviewRecord(Base):
    __tablename__ = "agent_task_memory_incident_reviews"
    __table_args__ = (
        UniqueConstraint(
            "incident_id",
            "reviewer_user_id",
            name="uq_agent_task_memory_incident_reviewer",
        ),
        CheckConstraint(
            "decision IN ('confirmed', 'dismissed')",
            name="ck_agent_task_memory_incident_review_decision",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    incident_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_task_memory_access_incidents.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    reviewer_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    decision: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )


class AgentTaskMemoryIncidentAssignee(Base):
    __tablename__ = "agent_task_memory_incident_assignees"
    __table_args__ = (
        UniqueConstraint(
            "incident_id",
            "responsible_user_id",
            name="uq_agent_task_memory_incident_assignee",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    incident_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_task_memory_access_incidents.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    responsible_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    assigned_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )


class AgentMemoryRiskReportRecord(Base):
    __tablename__ = "agent_memory_risk_report_records"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "agent_id",
            "sequence",
            name="uq_agent_memory_risk_report_sequence",
        ),
        CheckConstraint("sequence >= 1", name="ck_agent_memory_risk_report_sequence"),
        CheckConstraint(
            "signature_key_version >= 1",
            name="ck_agent_memory_risk_report_key_version",
        ),
        CheckConstraint(
            "char_length(signature) = 64 AND "
            "(previous_signature IS NULL OR char_length(previous_signature) = 64)",
            name="ck_agent_memory_risk_report_signatures",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    signature_key_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    signature: Mapped[str] = mapped_column(String(64), index=True)
    previous_signature: Mapped[str | None] = mapped_column(String(64))
    generated_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )


class AgentMemoryResponseExercise(Base):
    __tablename__ = "agent_memory_response_exercises"
    __table_args__ = (
        CheckConstraint("scenario = 'full'", name="ck_agent_memory_exercise_scenario"),
        CheckConstraint(
            "status IN ('passed', 'failed')",
            name="ck_agent_memory_exercise_status",
        ),
        CheckConstraint(
            "source IN ('manual', 'manual_schedule', 'worker_schedule')",
            name="ck_agent_memory_exercise_source",
        ),
        CheckConstraint(
            "duration_ms >= 0",
            name="ck_agent_memory_exercise_duration",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    scenario: Mapped[str] = mapped_column(String(16), default="full", server_default="full")
    status: Mapped[str] = mapped_column(String(16), index=True)
    checks: Mapped[dict[str, bool]] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(24), default="manual", server_default="manual")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )


class AgentMemoryRiskSigningKeyVersion(Base):
    __tablename__ = "agent_memory_risk_signing_key_versions"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "agent_id",
            "version",
            name="uq_agent_memory_risk_signing_key_version",
        ),
        CheckConstraint("version >= 1", name="ck_agent_memory_risk_signing_key_version"),
        CheckConstraint(
            "char_length(master_key_id) BETWEEN 6 AND 64",
            name="ck_agent_memory_risk_signing_master_key_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    master_key_id: Mapped[str] = mapped_column(String(64), index=True)
    activated_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )


class AgentMemoryExerciseSchedule(Base):
    __tablename__ = "agent_memory_exercise_schedules"
    __table_args__ = (
        UniqueConstraint("agent_id", name="uq_agent_memory_exercise_schedule_agent"),
        CheckConstraint(
            "cadence_hours BETWEEN 1 AND 720",
            name="ck_agent_memory_exercise_schedule_cadence",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    cadence_hours: Mapped[int] = mapped_column(Integer, default=168, server_default="168")
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AgentMemoryReencryptionJob(Base):
    __tablename__ = "agent_memory_reencryption_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_agent_memory_reencryption_job_status",
        ),
        CheckConstraint(
            "batch_size BETWEEN 1 AND 500",
            name="ck_agent_memory_reencryption_job_batch_size",
        ),
        CheckConstraint(
            "total_count >= 0 AND scanned_count >= 0 AND rotated_count >= 0 "
            "AND failed_count >= 0 AND scanned_count <= total_count "
            "AND rotated_count + failed_count <= scanned_count",
            name="ck_agent_memory_reencryption_job_counts",
        ),
        CheckConstraint(
            "(checkpoint_created_at IS NULL AND checkpoint_memory_id IS NULL) OR "
            "(checkpoint_created_at IS NOT NULL AND checkpoint_memory_id IS NOT NULL)",
            name="ck_agent_memory_reencryption_job_checkpoint",
        ),
        Index(
            "uq_agent_memory_reencryption_job_active",
            "company_id",
            "agent_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", index=True
    )
    target_master_key_id: Mapped[str] = mapped_column(String(64), index=True)
    batch_size: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    total_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    scanned_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rotated_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    checkpoint_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checkpoint_memory_id: Mapped[UUID | None] = mapped_column(nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64))
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AgentTaskMemoryAccessGrant(Base):
    __tablename__ = "agent_task_memory_access_grants"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "idempotency_key",
            name="uq_agent_task_memory_access_idempotency",
        ),
        CheckConstraint(
            "owner_agent_id <> recipient_agent_id",
            name="ck_agent_task_memory_access_distinct_agents",
        ),
        CheckConstraint(
            "purpose IN ('coordination', 'review', 'handoff')",
            name="ck_agent_task_memory_access_purpose",
        ),
        CheckConstraint(
            "status IN ('active', 'revoked', 'expired')",
            name="ck_agent_task_memory_access_status",
        ),
        CheckConstraint(
            "approval_status IN ('not_required', 'pending', 'approved', 'rejected')",
            name="ck_agent_task_memory_access_approval_status",
        ),
        CheckConstraint(
            "max_classification IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_agent_task_memory_access_classification",
        ),
        CheckConstraint(
            "max_cost_microunits BETWEEN 0 AND 2000000000",
            name="ck_agent_task_memory_access_cost",
        ),
        CheckConstraint(
            "(requires_human_approval = false AND approval_ttl_minutes IS NULL "
            "AND approval_expires_at IS NULL) OR "
            "(requires_human_approval = true AND approval_ttl_minutes BETWEEN 5 AND 240 "
            "AND approval_expires_at IS NOT NULL AND approval_expires_at > created_at "
            "AND approval_expires_at <= expires_at)",
            name="ck_agent_task_memory_access_approval_expiration",
        ),
        CheckConstraint(
            "(requires_human_approval = false AND approval_status = 'not_required' "
            "AND approved_by_user_id IS NULL AND approval_decided_at IS NULL) OR "
            "(requires_human_approval = true AND ((approval_status = 'pending' "
            "AND approved_by_user_id IS NULL AND approval_decided_at IS NULL) OR "
            "(approval_status IN ('approved', 'rejected') AND approved_by_user_id IS NOT NULL "
            "AND approval_decided_at IS NOT NULL AND approved_by_user_id <> granted_by_user_id)))",
            name="ck_agent_task_memory_access_approval",
        ),
        CheckConstraint(
            "max_entries BETWEEN 1 AND 5",
            name="ck_agent_task_memory_access_entries",
        ),
        CheckConstraint(
            "max_content_characters BETWEEN 64 AND 2000",
            name="ck_agent_task_memory_access_characters",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="ck_agent_task_memory_access_expiration",
        ),
        CheckConstraint(
            "(status IN ('active', 'expired') AND revoked_by_user_id IS NULL "
            "AND revoked_at IS NULL AND revocation_reason_fingerprint IS NULL) OR "
            "(status = 'revoked' AND revoked_by_user_id IS NOT NULL "
            "AND revoked_at IS NOT NULL AND revocation_reason_fingerprint IS NOT NULL)",
            name="ck_agent_task_memory_access_revocation",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    task_delegation_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_delegations.id", ondelete="CASCADE"), index=True
    )
    owner_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    recipient_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(24), index=True)
    allowed_classifications: Mapped[list[str]] = mapped_column(JSONB)
    allowed_tool_keys: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    max_classification: Mapped[str] = mapped_column(
        String(24), default="internal", server_default="internal"
    )
    max_cost_microunits: Mapped[int] = mapped_column(Integer, default=1000, server_default="1000")
    requires_human_approval: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    approval_status: Mapped[str] = mapped_column(
        String(16), default="not_required", server_default="not_required", index=True
    )
    approval_ttl_minutes: Mapped[int | None] = mapped_column(Integer)
    max_entries: Mapped[int] = mapped_column(Integer)
    max_content_characters: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(16), default="active", server_default="active", index=True
    )
    idempotency_key: Mapped[UUID] = mapped_column(index=True)
    granted_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    revoked_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    revocation_incident_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_task_memory_access_incidents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    revocation_reason_fingerprint: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    approval_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentTaskMemoryAccessTrace(Base):
    __tablename__ = "agent_task_memory_access_traces"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('consumed', 'blocked', 'empty', 'revoked_before_use', "
            "'expired_before_use', 'tool_policy_denied', 'aggregate_limit_denied', "
            "'cost_limit_denied')",
            name="ck_agent_task_memory_trace_outcome",
        ),
        CheckConstraint(
            "item_count >= 0 AND total_characters >= 0 AND blocked_items >= 0",
            name="ck_agent_task_memory_trace_counters",
        ),
        CheckConstraint(
            "estimated_cost_microunits >= 0",
            name="ck_agent_task_memory_trace_cost",
        ),
        CheckConstraint(
            "outcome NOT IN ('revoked_before_use', 'expired_before_use') OR "
            "(item_count = 0 AND total_characters = 0)",
            name="ck_agent_task_memory_trace_denied_empty",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    grant_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_task_memory_access_grants.id", ondelete="CASCADE"), index=True
    )
    task_delegation_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_delegations.id", ondelete="CASCADE"), index=True
    )
    agent_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), index=True
    )
    recipient_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), index=True
    )
    outcome: Mapped[str] = mapped_column(String(32), index=True)
    item_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_characters: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    blocked_items: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    estimated_cost_microunits: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )


class AgentMemoryConsentRevocation(Base):
    __tablename__ = "agent_memory_consent_revocations"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "agent_id",
            "subject_user_id",
            "consent_fingerprint",
            name="uq_agent_memory_consent_revocation",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    subject_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    subject_membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("company_users.id", ondelete="CASCADE"), index=True
    )
    consent_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    revoked_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
