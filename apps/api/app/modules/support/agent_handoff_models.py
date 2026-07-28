from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SupportAgentAssistRun(Base):
    __tablename__ = "support_agent_assist_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed','handoff_requested','completed','cancelled')",
            name="ck_support_agent_assist_runs_status",
        ),
        CheckConstraint(
            "recommendation IN ('respond','request_information','human_handoff')",
            name="ck_support_agent_assist_runs_recommendation",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("support_tickets.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="RESTRICT"), index=True)
    agent_version_id: Mapped[UUID] = mapped_column(ForeignKey("agent_versions.id", ondelete="RESTRICT"), index=True)
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="proposed", server_default="proposed", index=True)
    recommendation: Mapped[str] = mapped_column(String(32), index=True)
    reason_code: Mapped[str] = mapped_column(String(80), index=True)
    context_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    citation_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SupportHumanHandoff(Base):
    __tablename__ = "support_human_handoffs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('requested','accepted','rejected')",
            name="ck_support_human_handoffs_status",
        ),
        UniqueConstraint("company_id", "assist_run_id", name="uq_support_human_handoffs_run"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    assist_run_id: Mapped[UUID] = mapped_column(ForeignKey("support_agent_assist_runs.id", ondelete="CASCADE"), index=True)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("support_tickets.id", ondelete="CASCADE"), index=True)
    target_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    decided_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="requested", server_default="requested", index=True)
    reason_code: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
