"""Add weekly review calendars, absences and accepted handoffs.

Revision ID: 20260722_0088
Revises: 20260722_0087
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260722_0088"
down_revision: str | None = "20260722_0087"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_column(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def upgrade() -> None:
    policy = "agent_dispatch_review_sla_policies"
    op.add_column(
        policy,
        sa.Column(
            "on_call_weekdays",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[0,1,2,3,4,5,6]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_table(
        "agent_dispatch_review_on_call_exceptions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        _uuid_column("company_id"),
        _uuid_column("agent_id"),
        _uuid_column("policy_id"),
        _uuid_column("user_id"),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        _uuid_column("created_by_user_id"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ends_at > starts_at", name="ck_agent_review_on_call_exception_window"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'cancelled')",
            name="ck_agent_review_on_call_exception_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["policy_id"], ["agent_dispatch_review_sla_policies.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "agent_dispatch_review_on_call_handoffs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        _uuid_column("company_id"),
        _uuid_column("agent_id"),
        _uuid_column("policy_id"),
        _uuid_column("from_user_id"),
        _uuid_column("to_user_id"),
        _uuid_column("requested_by_user_id"),
        _uuid_column("responded_by_user_id", nullable=True),
        _uuid_column("request_idempotency_key"),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("ends_at > starts_at", name="ck_agent_review_on_call_handoff_window"),
        sa.CheckConstraint(
            "from_user_id <> to_user_id",
            name="ck_agent_review_on_call_handoff_distinct_users",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'cancelled', 'expired')",
            name="ck_agent_review_on_call_handoff_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["policy_id"], ["agent_dispatch_review_sla_policies.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["responded_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "request_idempotency_key",
            name="uq_agent_review_on_call_handoff_request",
        ),
    )
    for table, index_prefix, columns in (
        (
            "agent_dispatch_review_on_call_exceptions",
            "ix_agent_review_exc",
            ("company_id", "agent_id", "policy_id", "user_id", "starts_at", "ends_at"),
        ),
        (
            "agent_dispatch_review_on_call_handoffs",
            "ix_agent_review_handoff",
            (
                "company_id",
                "agent_id",
                "policy_id",
                "from_user_id",
                "to_user_id",
                "requested_by_user_id",
                "responded_by_user_id",
                "request_idempotency_key",
                "starts_at",
                "ends_at",
            ),
        ),
    ):
        for column in columns:
            op.create_index(f"{index_prefix}_{column}", table, [column])


def downgrade() -> None:
    op.drop_table("agent_dispatch_review_on_call_handoffs")
    op.drop_table("agent_dispatch_review_on_call_exceptions")
    op.drop_column("agent_dispatch_review_sla_policies", "on_call_weekdays")
