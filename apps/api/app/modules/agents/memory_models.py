from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
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
    max_entries: Mapped[int] = mapped_column(Integer)
    max_content_characters: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(16), default="active", server_default="active", index=True
    )
    idempotency_key: Mapped[UUID] = mapped_column(index=True)
    granted_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    revoked_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    revocation_reason_fingerprint: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentTaskMemoryAccessTrace(Base):
    __tablename__ = "agent_task_memory_access_traces"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('consumed', 'blocked', 'empty', 'revoked_before_use', 'expired_before_use')",
            name="ck_agent_task_memory_trace_outcome",
        ),
        CheckConstraint(
            "item_count >= 0 AND total_characters >= 0 AND blocked_items >= 0",
            name="ck_agent_task_memory_trace_counters",
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
