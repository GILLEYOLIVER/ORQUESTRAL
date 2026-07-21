"""Add safe agent run traces and execution modes.

Revision ID: 20260721_0033
Revises: 20260721_0032
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0033"
down_revision: str | None = "20260721_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("execution_mode", sa.String(length=16), server_default="live", nullable=False),
        sa.Column("status", sa.String(length=24), server_default="running", nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "planned_tool_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "completed_tool_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "denied_tool_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("step_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_microunits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_steps", sa.Integer(), nullable=False),
        sa.Column("max_runtime_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "execution_mode IN ('live', 'shadow', 'simulation')",
            name="ck_agent_runs_execution_mode",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'timed_out', 'awaiting_approval', 'simulated')",
            name="ck_agent_runs_status",
        ),
        sa.CheckConstraint(
            "step_count >= 0 AND total_tokens >= 0 AND cost_microunits >= 0 AND duration_ms >= 0",
            name="ck_agent_runs_metrics",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["agent_conversations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "agent_id",
        "agent_version_id",
        "conversation_id",
        "requested_by_user_id",
        "execution_mode",
        "status",
        "request_fingerprint",
        "started_at",
    ):
        op.create_index(f"ix_agent_runs_{column}", "agent_runs", [column])

    op.add_column(
        "agent_tool_runs", sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_index("ix_agent_tool_runs_agent_run_id", "agent_tool_runs", ["agent_run_id"])
    op.create_foreign_key(
        "fk_agent_tool_runs_run",
        "agent_tool_runs",
        "agent_runs",
        ["agent_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "agent_usage_records",
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_agent_usage_records_agent_run_id", "agent_usage_records", ["agent_run_id"])
    op.create_foreign_key(
        "fk_agent_usage_records_run",
        "agent_usage_records",
        "agent_runs",
        ["agent_run_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_agent_usage_records_run", "agent_usage_records", type_="foreignkey")
    op.drop_index("ix_agent_usage_records_agent_run_id", table_name="agent_usage_records")
    op.drop_column("agent_usage_records", "agent_run_id")
    op.drop_constraint("fk_agent_tool_runs_run", "agent_tool_runs", type_="foreignkey")
    op.drop_index("ix_agent_tool_runs_agent_run_id", table_name="agent_tool_runs")
    op.drop_column("agent_tool_runs", "agent_run_id")
    for column in reversed(
        (
            "company_id",
            "agent_id",
            "agent_version_id",
            "conversation_id",
            "requested_by_user_id",
            "execution_mode",
            "status",
            "request_fingerprint",
            "started_at",
        )
    ):
        op.drop_index(f"ix_agent_runs_{column}", table_name="agent_runs")
    op.drop_table("agent_runs")
