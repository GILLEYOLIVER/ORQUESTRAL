from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planning', 'active', 'on_hold', 'completed', 'cancelled')",
            name="ck_projects_status",
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="ck_projects_priority",
        ),
        CheckConstraint(
            "health IN ('unknown', 'on_track', 'at_risk', 'off_track')",
            name="ck_projects_health",
        ),
        CheckConstraint("budget_cents >= 0", name="ck_projects_budget"),
        Index("ix_projects_company_status", "company_id", "status"),
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
    portfolio_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("project_portfolios.id", ondelete="SET NULL"), index=True
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(180), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default="planning", server_default="planning", index=True
    )
    priority: Mapped[str] = mapped_column(
        String(20), default="normal", server_default="normal", index=True
    )
    health: Mapped[str] = mapped_column(
        String(20), default="unknown", server_default="unknown", index=True
    )
    budget_cents: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    start_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class ProjectTask(Base):
    __tablename__ = "project_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('todo', 'in_progress', 'blocked', 'done', 'cancelled')",
            name="ck_project_tasks_status",
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="ck_project_tasks_priority",
        ),
        CheckConstraint("position >= 0", name="ck_project_tasks_position"),
        CheckConstraint(
            "estimated_minutes >= 0 AND actual_minutes >= 0",
            name="ck_project_tasks_effort",
        ),
        Index("ix_project_tasks_project_status", "project_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    milestone_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("project_milestones.id", ondelete="SET NULL"), index=True
    )
    assignee_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default="todo", server_default="todo", index=True
    )
    priority: Mapped[str] = mapped_column(
        String(20), default="normal", server_default="normal", index=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    actual_minutes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class ProjectPortfolio(Base):
    __tablename__ = "project_portfolios"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_project_portfolio_company_name"),
        CheckConstraint("budget_cents >= 0", name="ck_project_portfolio_budget"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[str | None] = mapped_column(String(500))
    budget_cents: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class ProjectMilestone(Base):
    __tablename__ = "project_milestones"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'at_risk', 'completed', 'cancelled')",
            name="ck_project_milestones_status",
        ),
        UniqueConstraint("project_id", "name", name="uq_project_milestone_project_name"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date]
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class ProjectRisk(Base):
    __tablename__ = "project_risks"
    __table_args__ = (
        CheckConstraint(
            "probability >= 1 AND probability <= 5", name="ck_project_risk_probability"
        ),
        CheckConstraint("impact >= 1 AND impact <= 5", name="ck_project_risk_impact"),
        CheckConstraint(
            "status IN ('open', 'mitigating', 'accepted', 'closed')",
            name="ck_project_risk_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(180))
    description_encrypted: Mapped[str] = mapped_column(Text)
    mitigation_encrypted: Mapped[str | None] = mapped_column(Text)
    probability: Mapped[int] = mapped_column(Integer)
    impact: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="open", server_default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member_project_user"),
        CheckConstraint(
            "allocation_percent >= 1 AND allocation_percent <= 100",
            name="ck_project_member_allocation",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(120), default="Membro")
    allocation_percent: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


class ProjectTaskDependency(Base):
    __tablename__ = "project_task_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "predecessor_task_id",
            "successor_task_id",
            name="uq_project_task_dependency_pair",
        ),
        CheckConstraint(
            "predecessor_task_id <> successor_task_id",
            name="ck_project_task_dependency_not_self",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    predecessor_task_id: Mapped[UUID] = mapped_column(
        ForeignKey("project_tasks.id", ondelete="CASCADE"), index=True
    )
    successor_task_id: Mapped[UUID] = mapped_column(
        ForeignKey("project_tasks.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
