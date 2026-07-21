"""Trace minimized task memory consumed by delegation execution.

Revision ID: 20260721_0050
Revises: 20260721_0049
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0050"
down_revision: str | None = "20260721_0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_task_memory_access_traces",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("grant_id", sa.Uuid(), nullable=False),
        sa.Column("task_delegation_id", sa.Uuid(), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=True),
        sa.Column("owner_agent_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_agent_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("item_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_characters", sa.Integer(), server_default="0", nullable=False),
        sa.Column("blocked_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "outcome IN ('consumed', 'blocked', 'empty', 'revoked_before_use', 'expired_before_use')",
            name="ck_agent_task_memory_trace_outcome",
        ),
        sa.CheckConstraint(
            "item_count >= 0 AND total_characters >= 0 AND blocked_items >= 0",
            name="ck_agent_task_memory_trace_counters",
        ),
        sa.CheckConstraint(
            "outcome NOT IN ('revoked_before_use', 'expired_before_use') OR "
            "(item_count = 0 AND total_characters = 0)",
            name="ck_agent_task_memory_trace_denied_empty",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["grant_id"], ["agent_task_memory_access_grants.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_delegation_id"], ["agent_delegations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recipient_agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "grant_id",
        "task_delegation_id",
        "agent_run_id",
        "owner_agent_id",
        "recipient_agent_id",
        "outcome",
        "created_at",
    ):
        op.create_index(
            f"ix_agent_task_memory_trace_{column}",
            "agent_task_memory_access_traces",
            [column],
        )


def downgrade() -> None:
    op.drop_table("agent_task_memory_access_traces")
