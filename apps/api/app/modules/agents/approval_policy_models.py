from __future__ import annotations

from datetime import datetime
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


class AgentApprovalPolicyVersion(Base):
    __tablename__ = "agent_approval_policy_versions"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "agent_id",
            "policy_key",
            "version",
            name="uq_agent_approval_policy_version",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'retired')",
            name="ck_agent_approval_policy_status",
        ),
        CheckConstraint(
            "effect IN ('allow', 'require_approval', 'deny')",
            name="ck_agent_approval_policy_effect",
        ),
        CheckConstraint(
            "priority BETWEEN 0 AND 1000",
            name="ck_agent_approval_policy_priority",
        ),
        CheckConstraint(
            "approval_ttl_minutes BETWEEN 5 AND 10080",
            name="ck_agent_approval_policy_ttl",
        ),
        CheckConstraint(
            "min_amount_microunits IS NULL OR min_amount_microunits >= 0",
            name="ck_agent_approval_policy_min_amount",
        ),
        CheckConstraint(
            "max_amount_microunits IS NULL OR max_amount_microunits >= 0",
            name="ck_agent_approval_policy_max_amount",
        ),
        CheckConstraint(
            "min_amount_microunits IS NULL OR max_amount_microunits IS NULL "
            "OR max_amount_microunits >= min_amount_microunits",
            name="ck_agent_approval_policy_amount_range",
        ),
        CheckConstraint(
            "(escalation_user_id IS NULL AND escalation_after_minutes IS NULL) OR "
            "(escalation_user_id IS NOT NULL AND assigned_user_id IS NOT NULL "
            "AND escalation_after_minutes BETWEEN 5 AND approval_ttl_minutes - 1 "
            "AND escalation_user_id <> assigned_user_id)",
            name="ck_agent_approval_policy_escalation",
        ),
        CheckConstraint(
            "effect = 'require_approval' OR "
            "(assigned_user_id IS NULL AND escalation_user_id IS NULL "
            "AND escalation_after_minutes IS NULL)",
            name="ck_agent_approval_policy_approvers_effect",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    policy_key: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(
        String(16), default="draft", server_default="draft", index=True
    )
    effect: Mapped[str] = mapped_column(String(24), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    tool_key: Mapped[str | None] = mapped_column(String(160), index=True)
    amount_field: Mapped[str | None] = mapped_column(String(160))
    min_amount_microunits: Mapped[int | None] = mapped_column(Integer)
    max_amount_microunits: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(3))
    context_conditions: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    approval_ttl_minutes: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    assigned_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    escalation_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    escalation_after_minutes: Mapped[int | None] = mapped_column(Integer)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
