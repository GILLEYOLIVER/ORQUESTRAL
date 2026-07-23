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
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentExecutionSchedule(Base):
    __tablename__ = "agent_execution_schedules"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "agent_id",
            "schedule_key",
            "version",
            name="uq_agent_execution_schedule_version",
        ),
        CheckConstraint("version >= 1", name="ck_agent_execution_schedule_version"),
        CheckConstraint(
            "status IN ('draft', 'published', 'paused', 'retired')",
            name="ck_agent_execution_schedule_status",
        ),
        CheckConstraint(
            "cadence_minutes BETWEEN 5 AND 10080",
            name="ck_agent_execution_schedule_cadence",
        ),
        Index(
            "ix_agent_execution_schedule_due",
            "status",
            "next_run_at",
            "company_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    agent_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_versions.id", ondelete="RESTRICT"), index=True
    )
    schedule_key: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    name: Mapped[str] = mapped_column(String(160))
    objective: Mapped[str] = mapped_column(String(1000))
    cadence_minutes: Mapped[int] = mapped_column(Integer)
    required_tool_keys: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class AgentEventTrigger(Base):
    __tablename__ = "agent_event_triggers"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "agent_id",
            "trigger_key",
            "version",
            name="uq_agent_event_trigger_version",
        ),
        CheckConstraint("version >= 1", name="ck_agent_event_trigger_version"),
        CheckConstraint(
            "status IN ('draft', 'published', 'paused', 'retired')",
            name="ck_agent_event_trigger_status",
        ),
        CheckConstraint("min_event_version >= 1", name="ck_agent_event_trigger_min_version"),
        CheckConstraint(
            "max_event_version IS NULL OR max_event_version >= min_event_version",
            name="ck_agent_event_trigger_version_range",
        ),
        Index(
            "ix_agent_event_trigger_match",
            "status",
            "event_type",
            "company_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    agent_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_versions.id", ondelete="RESTRICT"), index=True
    )
    trigger_key: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    name: Mapped[str] = mapped_column(String(160))
    event_type: Mapped[str] = mapped_column(String(160), index=True)
    min_event_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    max_event_version: Mapped[int | None] = mapped_column(Integer)
    objective: Mapped[str] = mapped_column(String(1000))
    required_tool_keys: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class AgentCredentialBinding(Base):
    __tablename__ = "agent_credential_bindings"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "agent_id", "tool_key", name="uq_agent_credential_binding_tool"
        ),
        Index("ix_agent_credential_binding_lookup", "company_id", "agent_id", "enabled"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    tool_key: Mapped[str] = mapped_column(String(160), index=True)
    credential_id: Mapped[UUID] = mapped_column(
        ForeignKey("integration_credentials.id", ondelete="RESTRICT"), index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class AgentRuntimeDispatch(Base):
    __tablename__ = "agent_runtime_dispatches"
    __table_args__ = (
        UniqueConstraint("schedule_id", "scheduled_for", name="uq_agent_runtime_schedule_dispatch"),
        UniqueConstraint("trigger_id", "source_event_id", name="uq_agent_runtime_event_dispatch"),
        CheckConstraint(
            "source_type IN ('schedule', 'event')", name="ck_agent_runtime_dispatch_source"
        ),
        CheckConstraint("status IN ('ready', 'blocked')", name="ck_agent_runtime_dispatch_status"),
        CheckConstraint(
            "(source_type = 'schedule' AND schedule_id IS NOT NULL AND trigger_id IS NULL) OR "
            "(source_type = 'event' AND trigger_id IS NOT NULL AND schedule_id IS NULL "
            "AND source_event_id IS NOT NULL)",
            name="ck_agent_runtime_dispatch_reference",
        ),
        Index("ix_agent_runtime_dispatch_queue", "status", "created_at", "company_id"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    agent_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_versions.id", ondelete="RESTRICT"), index=True
    )
    schedule_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_execution_schedules.id", ondelete="CASCADE"), index=True
    )
    trigger_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_event_triggers.id", ondelete="CASCADE"), index=True
    )
    source_event_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("outbox_events.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    reason_code: Mapped[str | None] = mapped_column(String(120))
    objective_fingerprint: Mapped[str] = mapped_column(String(64))
    required_tool_keys: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    credential_binding_ids: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
