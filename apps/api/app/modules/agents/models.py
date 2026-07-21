from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive')", name="ck_agents_status"),
        CheckConstraint("provider IN ('local', 'openai_compatible')", name="ck_agents_provider"),
        CheckConstraint("temperature >= 0 AND temperature <= 2", name="ck_agents_temperature"),
        CheckConstraint(
            "max_input_tokens > 0 AND max_output_tokens > 0", name="ck_agents_token_limits"
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
    instructions: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(40), default="local", server_default="local")
    model: Mapped[str] = mapped_column(
        String(120), default="orkestral-local", server_default="orkestral-local"
    )
    temperature: Mapped[float] = mapped_column(Float, default=0.2, server_default="0.2")
    max_input_tokens: Mapped[int] = mapped_column(Integer, default=4096, server_default="4096")
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=1024, server_default="1024")
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    knowledge_base_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", index=True
    )
    active_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class AgentVersion(Base):
    __tablename__ = "agent_versions"
    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_version"),
        CheckConstraint(
            "status IN ('draft', 'published', 'retired')", name="ck_agent_versions_status"
        ),
        CheckConstraint("autonomy_level >= 0 AND autonomy_level <= 4", name="ck_agent_autonomy"),
        CheckConstraint("max_steps > 0 AND max_steps <= 100", name="ck_agent_version_steps"),
        CheckConstraint(
            "max_runtime_seconds > 0 AND max_runtime_seconds <= 3600",
            name="ck_agent_version_runtime",
        ),
        CheckConstraint("max_cost_per_run_microunits >= 0", name="ck_agent_version_run_cost"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", index=True
    )
    instructions: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(120))
    temperature: Mapped[float] = mapped_column(Float)
    max_input_tokens: Mapped[int] = mapped_column(Integer)
    max_output_tokens: Mapped[int] = mapped_column(Integer)
    memory_enabled: Mapped[bool] = mapped_column(Boolean)
    knowledge_base_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True
    )
    autonomy_level: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    max_steps: Mapped[int] = mapped_column(Integer, default=12, server_default="12")
    max_runtime_seconds: Mapped[int] = mapped_column(Integer, default=120, server_default="120")
    max_cost_per_run_microunits: Mapped[int] = mapped_column(
        Integer, default=1_000_000, server_default="1000000"
    )
    checksum: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentBudget(Base):
    __tablename__ = "agent_budgets"
    __table_args__ = (
        UniqueConstraint("agent_id", name="uq_agent_budgets_agent"),
        CheckConstraint(
            "limit_microunits >= 0 AND reserved_microunits >= 0 AND consumed_microunits >= 0",
            name="ck_agent_budget_amounts",
        ),
        CheckConstraint("cycle_ends_at > cycle_started_at", name="ck_agent_budget_cycle"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    limit_microunits: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reserved_microunits: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    consumed_microunits: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    hard_limit: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    cycle_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cycle_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class AgentTool(Base):
    __tablename__ = "agent_tools"
    __table_args__ = (UniqueConstraint("agent_id", "tool_key", name="uq_agent_tools_agent_key"),)

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    tool_key: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(500))
    input_schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    required_permission: Mapped[str | None] = mapped_column(String(120))
    risk_level: Mapped[str] = mapped_column(String(16), default="low", server_default="low")
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class AgentConversation(Base):
    __tablename__ = "agent_conversations"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'closed')", name="ck_agent_conversations_status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(
        String(20), default="open", server_default="open", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class AgentMessage(Base):
    __tablename__ = "agent_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('system', 'user', 'assistant', 'tool')", name="ck_agent_messages_role"
        ),
        CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0 AND total_tokens >= 0",
            name="ck_agent_messages_tokens",
        ),
        CheckConstraint("cost_microunits >= 0", name="ck_agent_messages_cost"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), index=True)
    content: Mapped[str] = mapped_column(Text)
    tool_call: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    provider: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(120))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cost_microunits: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )


class AgentToolRun(Base):
    __tablename__ = "agent_tool_runs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('requested', 'awaiting_confirmation', 'approved', 'rejected', 'executing', 'completed', 'failed')",
            name="ck_agent_tool_runs_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    agent_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="SET NULL"), index=True
    )
    message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_messages.id", ondelete="SET NULL"), index=True
    )
    tool_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_tools.id", ondelete="RESTRICT"), index=True
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    state: Mapped[str] = mapped_column(
        String(30), default="requested", server_default="requested", index=True
    )
    arguments: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    result_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    error_summary: Mapped[str | None] = mapped_column(Text)
    requires_confirmation: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    rejected_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class AgentUsageRecord(Base):
    __tablename__ = "agent_usage_records"
    __table_args__ = (
        CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0 AND total_tokens >= 0",
            name="ck_agent_usage_tokens",
        ),
        CheckConstraint("cost_microunits >= 0", name="ck_agent_usage_cost"),
        CheckConstraint("duration_ms >= 0", name="ck_agent_usage_duration"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    agent_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="SET NULL"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40), index=True)
    model: Mapped[str] = mapped_column(String(120), index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cost_microunits: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tool_key: Mapped[str | None] = mapped_column(String(120), index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    result_status: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
