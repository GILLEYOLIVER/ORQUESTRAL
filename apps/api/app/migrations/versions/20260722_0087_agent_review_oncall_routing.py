"""Add agent review on-call routing and assignment history.

Revision ID: 20260722_0087
Revises: 20260722_0086
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260722_0087"
down_revision: str | None = "20260722_0086"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    policy = "agent_dispatch_review_sla_policies"
    op.add_column(
        policy,
        sa.Column("acknowledgement_minutes", sa.Integer(), server_default="15", nullable=False),
    )
    op.add_column(
        policy,
        sa.Column(
            "on_call_user_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        policy, sa.Column("on_call_timezone", sa.String(64), server_default="UTC", nullable=False)
    )
    op.add_column(
        policy, sa.Column("on_call_start_hour", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        policy, sa.Column("on_call_end_hour", sa.Integer(), server_default="24", nullable=False)
    )
    op.create_check_constraint(
        "ck_agent_dispatch_review_sla_acknowledgement",
        policy,
        "acknowledgement_minutes BETWEEN 1 AND 1440",
    )
    op.create_check_constraint(
        "ck_agent_dispatch_review_sla_on_call_window",
        policy,
        "on_call_start_hour BETWEEN 0 AND 23 AND on_call_end_hour BETWEEN 1 AND 24 "
        "AND on_call_start_hour < on_call_end_hour",
    )
    op.create_table(
        "agent_dispatch_review_assignments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_assignment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("acknowledged_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source IN ('on_call', 'manual', 'fallback')",
            name="ck_agent_dispatch_review_assignment_source",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'acknowledged', 'reassigned', 'closed')",
            name="ck_agent_dispatch_review_assignment_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["review_id"], ["agent_dispatch_reviews.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["previous_assignment_id"],
            ["agent_dispatch_review_assignments.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["acknowledged_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "agent_id",
        "review_id",
        "previous_assignment_id",
        "assigned_to_user_id",
        "assigned_by_user_id",
        "acknowledged_by_user_id",
        "ended_at",
    ):
        op.create_index(
            f"ix_agent_dispatch_review_assignments_{column}",
            "agent_dispatch_review_assignments",
            [column],
        )
    op.create_index(
        "uq_agent_dispatch_review_assignment_active",
        "agent_dispatch_review_assignments",
        ["company_id", "review_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("agent_dispatch_review_assignments")
    policy = "agent_dispatch_review_sla_policies"
    op.drop_constraint("ck_agent_dispatch_review_sla_on_call_window", policy, type_="check")
    op.drop_constraint("ck_agent_dispatch_review_sla_acknowledgement", policy, type_="check")
    for column in (
        "on_call_end_hour",
        "on_call_start_hour",
        "on_call_timezone",
        "on_call_user_ids",
        "acknowledgement_minutes",
    ):
        op.drop_column(policy, column)
