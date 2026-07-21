from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
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


class AgentEvaluationSuite(Base):
    __tablename__ = "agent_evaluation_suites"
    __table_args__ = (
        UniqueConstraint("agent_version_id", name="uq_agent_evaluation_suite_version"),
        CheckConstraint("minimum_score BETWEEN 0 AND 100", name="ck_agent_eval_suite_score"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    agent_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_versions.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    minimum_score: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )


class AgentEvaluationCase(Base):
    __tablename__ = "agent_evaluation_cases"
    __table_args__ = (UniqueConstraint("suite_id", "name", name="uq_agent_eval_case_name"),)

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    suite_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_evaluation_suites.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    input_text: Mapped[str] = mapped_column(Text)
    expected_blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    expected_tool_keys: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    forbidden_tool_keys: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


class AgentEvaluationRun(Base):
    __tablename__ = "agent_evaluation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'passed', 'failed')", name="ck_agent_eval_run_status"
        ),
        CheckConstraint(
            "total_cases >= 0 AND passed_cases >= 0 AND score BETWEEN 0 AND 100",
            name="ck_agent_eval_run_metrics",
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
        ForeignKey("agent_versions.id", ondelete="CASCADE"), index=True
    )
    suite_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_evaluation_suites.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default="running", server_default="running", index=True
    )
    total_cases: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    passed_cases: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentEvaluationResult(Base):
    __tablename__ = "agent_evaluation_results"
    __table_args__ = (UniqueConstraint("run_id", "case_id", name="uq_agent_eval_result_case"),)

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_evaluation_runs.id", ondelete="CASCADE"), index=True
    )
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_evaluation_cases.id", ondelete="CASCADE"), index=True
    )
    passed: Mapped[bool] = mapped_column(Boolean, index=True)
    actual_blocked: Mapped[bool] = mapped_column(Boolean)
    planned_tool_keys: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    failure_codes: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
