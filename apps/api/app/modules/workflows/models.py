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
            "source IN ('manual', 'webhook', 'schedule', 'system')",
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
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    external_execution_id: Mapped[str | None] = mapped_column(String(80), index=True)
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
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
