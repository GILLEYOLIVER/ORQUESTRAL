"""Persist safe operational steps for agent runs.

Revision ID: 20260722_0082
Revises: 20260722_0081
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260722_0082"
down_revision: str | None = "20260722_0081"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_run_steps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("summary_code", sa.String(length=80), nullable=False),
        sa.Column("tool_key", sa.String(length=120), nullable=True),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("output_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("sequence > 0", name="ck_agent_run_steps_sequence"),
        sa.CheckConstraint("step_type IN ('provider', 'tool')", name="ck_agent_run_steps_type"),
        sa.CheckConstraint(
            "status IN ('planned', 'completed', 'blocked', 'failed', "
            "'awaiting_approval', 'simulated', 'timed_out')",
            name="ck_agent_run_steps_status",
        ),
        sa.CheckConstraint("duration_ms >= 0", name="ck_agent_run_steps_duration"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_run_id"], ["agent_tool_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_run_id", "sequence", name="uq_agent_run_steps_sequence"),
    )
    for column in (
        "company_id",
        "agent_id",
        "agent_run_id",
        "tool_run_id",
        "step_type",
        "status",
        "summary_code",
        "tool_key",
        "input_fingerprint",
        "output_fingerprint",
        "error_code",
        "started_at",
    ):
        op.create_index(f"ix_agent_run_steps_{column}", "agent_run_steps", [column])


def downgrade() -> None:
    op.drop_table("agent_run_steps")
