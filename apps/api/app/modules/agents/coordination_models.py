from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
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


class AgentTaskContract(Base):
    __tablename__ = "agent_task_contracts"
    __table_args__ = (
        UniqueConstraint(
            "supervisor_agent_id", "worker_agent_id", "name", name="uq_agent_task_contract_pair"
        ),
        CheckConstraint(
            "supervisor_agent_id <> worker_agent_id", name="ck_agent_task_contract_distinct_agents"
        ),
        CheckConstraint("max_steps BETWEEN 1 AND 100", name="ck_agent_task_contract_steps"),
        CheckConstraint("max_cost_microunits >= 0", name="ck_agent_task_contract_cost"),
        CheckConstraint(
            "deadline_seconds BETWEEN 1 AND 86400", name="ck_agent_task_contract_deadline"
        ),
        CheckConstraint(
            "max_delegation_depth BETWEEN 1 AND 5", name="ck_agent_task_contract_depth"
        ),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_agent_task_contract_status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    supervisor_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    worker_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    allowed_tool_keys: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    required_context_keys: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    max_steps: Mapped[int] = mapped_column(Integer)
    max_cost_microunits: Mapped[int] = mapped_column(Integer)
    deadline_seconds: Mapped[int] = mapped_column(Integer, default=300, server_default="300")
    max_delegation_depth: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[str] = mapped_column(
        String(16), default="active", server_default="active", index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )


class AgentDelegation(Base):
    __tablename__ = "agent_delegations"
    __table_args__ = (
        UniqueConstraint("company_id", "idempotency_key", name="uq_agent_delegation_idempotency"),
        CheckConstraint(
            "status IN ('queued', 'in_progress', 'awaiting_approval', 'completed', 'failed', 'cancelled')",
            name="ck_agent_delegation_status",
        ),
        CheckConstraint("depth BETWEEN 1 AND 5", name="ck_agent_delegation_depth"),
        CheckConstraint(
            "reserved_cost_microunits >= 0 AND consumed_cost_microunits >= 0",
            name="ck_agent_delegation_cost",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_task_contracts.id", ondelete="RESTRICT"), index=True
    )
    parent_delegation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_delegations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    supervisor_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), index=True
    )
    assigned_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), index=True
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    idempotency_key: Mapped[UUID] = mapped_column(index=True)
    objective_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    result_fingerprint: Mapped[str | None] = mapped_column(String(64))
    context_keys: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    status: Mapped[str] = mapped_column(
        String(20), default="queued", server_default="queued", index=True
    )
    depth: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    reserved_cost_microunits: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    consumed_cost_microunits: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    claimed_by: Mapped[str | None] = mapped_column(String(160))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentDelegationPayload(Base):
    __tablename__ = "agent_delegation_payloads"
    __table_args__ = (UniqueConstraint("delegation_id", name="uq_agent_delegation_payload"),)

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    delegation_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_delegations.id", ondelete="CASCADE"), index=True
    )
    encrypted_objective: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    destroyed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AgentDelegationApproval(Base):
    __tablename__ = "agent_delegation_approvals"
    __table_args__ = (
        UniqueConstraint("approval_request_id", name="uq_agent_delegation_approval_request"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired')",
            name="ck_agent_delegation_approval_status",
        ),
        CheckConstraint(
            "(escalation_user_id IS NULL AND escalate_at IS NULL) OR "
            "(escalation_user_id IS NOT NULL AND escalate_at IS NOT NULL)",
            name="ck_agent_delegation_approval_escalation",
        ),
        CheckConstraint(
            "escalate_at IS NULL OR escalate_at < expires_at",
            name="ck_agent_delegation_approval_escalation_deadline",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    delegation_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_delegations.id", ondelete="CASCADE"), index=True
    )
    approval_request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("approval_requests.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tool_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_tools.id", ondelete="RESTRICT"), index=True
    )
    policy_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_approval_policy_versions.id", ondelete="SET NULL"), index=True
    )
    current_policy_stage_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_approval_policy_stages.id", ondelete="SET NULL"), index=True
    )
    encrypted_arguments: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", index=True
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    decided_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    escalation_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    escalate_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentDelegationApprovalVote(Base):
    __tablename__ = "agent_delegation_approval_votes"
    __table_args__ = (
        UniqueConstraint(
            "delegation_approval_id",
            "policy_stage_id",
            "represented_user_id",
            name="uq_agent_delegation_approval_vote",
        ),
        CheckConstraint(
            "decision IN ('approved', 'rejected')",
            name="ck_agent_delegation_approval_vote_decision",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    delegation_approval_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_delegation_approvals.id", ondelete="CASCADE"), index=True
    )
    policy_stage_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_approval_policy_stages.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    represented_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    decision: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )


class AgentHandoff(Base):
    __tablename__ = "agent_handoffs"
    __table_args__ = (
        CheckConstraint("from_agent_id <> to_agent_id", name="ck_agent_handoff_distinct_agents"),
        CheckConstraint(
            "status IN ('requested', 'accepted', 'rejected')", name="ck_agent_handoff_status"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    delegation_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_delegations.id", ondelete="CASCADE"), index=True
    )
    from_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), index=True
    )
    to_agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), index=True
    )
    reason_code: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(
        String(16), default="requested", server_default="requested", index=True
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    decided_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
