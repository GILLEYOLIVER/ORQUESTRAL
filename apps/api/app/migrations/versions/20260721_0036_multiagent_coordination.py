"""Add governed multi-agent task coordination.

Revision ID: 20260721_0036
Revises: 20260721_0035
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0036"
down_revision: str | None = "20260721_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _uuid(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def _indexes(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def _drop_indexes(table: str, columns: tuple[str, ...]) -> None:
    for column in reversed(columns):
        op.drop_index(f"ix_{table}_{column}", table_name=table)


def upgrade() -> None:
    op.create_table(
        "agent_task_contracts",
        _id(),
        _uuid("company_id"),
        _uuid("supervisor_agent_id"),
        _uuid("worker_agent_id"),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "allowed_tool_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "required_context_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("max_steps", sa.Integer(), nullable=False),
        sa.Column("max_cost_microunits", sa.Integer(), nullable=False),
        sa.Column("deadline_seconds", sa.Integer(), server_default="300", nullable=False),
        sa.Column("max_delegation_depth", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        _uuid("created_by_user_id"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "supervisor_agent_id <> worker_agent_id",
            name="ck_agent_task_contract_distinct_agents",
        ),
        sa.CheckConstraint("max_steps BETWEEN 1 AND 100", name="ck_agent_task_contract_steps"),
        sa.CheckConstraint("max_cost_microunits >= 0", name="ck_agent_task_contract_cost"),
        sa.CheckConstraint(
            "deadline_seconds BETWEEN 1 AND 86400", name="ck_agent_task_contract_deadline"
        ),
        sa.CheckConstraint(
            "max_delegation_depth BETWEEN 1 AND 5", name="ck_agent_task_contract_depth"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')", name="ck_agent_task_contract_status"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supervisor_agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["worker_agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "supervisor_agent_id",
            "worker_agent_id",
            "name",
            name="uq_agent_task_contract_pair",
        ),
    )
    _indexes(
        "agent_task_contracts",
        (
            "company_id",
            "supervisor_agent_id",
            "worker_agent_id",
            "status",
            "created_by_user_id",
            "created_at",
        ),
    )
    op.create_table(
        "agent_delegations",
        _id(),
        _uuid("company_id"),
        _uuid("contract_id"),
        _uuid("parent_delegation_id", nullable=True),
        _uuid("supervisor_agent_id"),
        _uuid("assigned_agent_id"),
        _uuid("requested_by_user_id"),
        _uuid("idempotency_key"),
        sa.Column("objective_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_fingerprint", sa.String(length=64), nullable=True),
        sa.Column(
            "context_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("depth", sa.Integer(), server_default="1", nullable=False),
        sa.Column("reserved_cost_microunits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("consumed_cost_microunits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'in_progress', 'completed', 'failed', 'cancelled')",
            name="ck_agent_delegation_status",
        ),
        sa.CheckConstraint("depth BETWEEN 1 AND 5", name="ck_agent_delegation_depth"),
        sa.CheckConstraint(
            "reserved_cost_microunits >= 0 AND consumed_cost_microunits >= 0",
            name="ck_agent_delegation_cost",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contract_id"], ["agent_task_contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["parent_delegation_id"], ["agent_delegations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["supervisor_agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "idempotency_key", name="uq_agent_delegation_idempotency"
        ),
    )
    _indexes(
        "agent_delegations",
        (
            "company_id",
            "contract_id",
            "parent_delegation_id",
            "supervisor_agent_id",
            "assigned_agent_id",
            "requested_by_user_id",
            "idempotency_key",
            "objective_fingerprint",
            "status",
            "due_at",
            "created_at",
        ),
    )
    op.create_table(
        "agent_handoffs",
        _id(),
        _uuid("company_id"),
        _uuid("delegation_id"),
        _uuid("from_agent_id"),
        _uuid("to_agent_id"),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="requested", nullable=False),
        _uuid("requested_by_user_id"),
        _uuid("decided_by_user_id", nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("from_agent_id <> to_agent_id", name="ck_agent_handoff_distinct_agents"),
        sa.CheckConstraint(
            "status IN ('requested', 'accepted', 'rejected')", name="ck_agent_handoff_status"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delegation_id"], ["agent_delegations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(
        "agent_handoffs",
        (
            "company_id",
            "delegation_id",
            "from_agent_id",
            "to_agent_id",
            "status",
            "requested_by_user_id",
            "created_at",
        ),
    )


def downgrade() -> None:
    _drop_indexes(
        "agent_handoffs",
        (
            "company_id",
            "delegation_id",
            "from_agent_id",
            "to_agent_id",
            "status",
            "requested_by_user_id",
            "created_at",
        ),
    )
    op.drop_table("agent_handoffs")
    _drop_indexes(
        "agent_delegations",
        (
            "company_id",
            "contract_id",
            "parent_delegation_id",
            "supervisor_agent_id",
            "assigned_agent_id",
            "requested_by_user_id",
            "idempotency_key",
            "objective_fingerprint",
            "status",
            "due_at",
            "created_at",
        ),
    )
    op.drop_table("agent_delegations")
    _drop_indexes(
        "agent_task_contracts",
        (
            "company_id",
            "supervisor_agent_id",
            "worker_agent_id",
            "status",
            "created_by_user_id",
            "created_at",
        ),
    )
    op.drop_table("agent_task_contracts")
