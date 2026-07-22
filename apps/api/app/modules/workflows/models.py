from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Workflow(Base):
    __tablename__ = "workflows"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'inactive', 'error')",
            name="ck_workflows_status",
        ),
        CheckConstraint(
            "sync_status IN ('pending', 'synced', 'error')",
            name="ck_workflows_sync_status",
        ),
        CheckConstraint("version >= 1", name="ck_workflows_version"),
        UniqueConstraint(
            "provider_key",
            "provider_workflow_id",
            name="uq_workflows_provider_reference",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str | None] = mapped_column(String(500))
    definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    n8n_workflow_id: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    n8n_version_id: Mapped[str | None] = mapped_column(String(80))
    provider_key: Mapped[str] = mapped_column(
        String(80), default="n8n", server_default="n8n", index=True
    )
    provider_workflow_id: Mapped[str | None] = mapped_column(String(120), index=True)
    provider_version_id: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", index=True
    )
    sync_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", index=True
    )
    internal_webhook_path: Mapped[str] = mapped_column(String(160), unique=True)
    public_webhook_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    encrypted_webhook_secret: Mapped[bytes] = mapped_column(LargeBinary)
    last_error: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    __table_args__ = (
        CheckConstraint(
            "source IN ('manual', 'webhook', 'schedule', 'system', 'domain_event')",
            name="ck_workflow_executions_source",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'success', 'error', 'canceled', 'waiting')",
            name="ck_workflow_executions_status",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_workflow_executions_duration",
        ),
        CheckConstraint(
            "compensation_status IN ('not_required', 'pending', 'acknowledged')",
            name="ck_workflow_executions_compensation_status",
        ),
        CheckConstraint(
            "remote_cancel_status IN ('not_requested', 'unsupported', 'requested', 'confirmed', 'failed')",
            name="ck_workflow_executions_remote_cancel_status",
        ),
        UniqueConstraint(
            "company_id", "workflow_id", "source_event_id", name="uq_workflow_execution_event"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )
    source_event_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("outbox_events.id", ondelete="SET NULL"), index=True
    )
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    canceled_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    external_execution_id: Mapped[str | None] = mapped_column(String(80), index=True)
    provider_key: Mapped[str] = mapped_column(
        String(80), default="n8n", server_default="n8n", index=True
    )
    source: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="queued", server_default="queued", index=True
    )
    input_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    output_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    error_summary: Mapped[str | None] = mapped_column(Text)
    cancel_reason: Mapped[str | None] = mapped_column(String(300))
    compensation_status: Mapped[str] = mapped_column(
        String(24), default="not_required", server_default="not_required", index=True
    )
    compensation_plan: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    remote_cancel_status: Mapped[str] = mapped_column(
        String(24), default="not_requested", server_default="not_requested"
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )


class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "version", name="uq_workflow_versions_workflow_version"),
        CheckConstraint("version >= 1", name="ck_workflow_versions_version"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(String(500))
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    change_summary: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )


class WorkflowProviderCircuit(Base):
    __tablename__ = "workflow_provider_circuits"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "provider", name="uq_workflow_provider_circuit_company_provider"
        ),
        CheckConstraint(
            "state IN ('closed', 'open', 'half_open')",
            name="ck_workflow_provider_circuit_state",
        ),
        CheckConstraint("failure_count >= 0", name="ck_workflow_provider_circuit_failures"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(20), default="closed", server_default="closed")
    failure_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_failure_code: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )
