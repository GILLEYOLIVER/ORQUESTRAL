"""Add governed agent dispatch execution state.

Revision ID: 20260722_0084
Revises: 20260722_0083
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260722_0084"
down_revision: str | None = "20260722_0083"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_source_execution_columns(table: str, prefix: str) -> None:
    op.add_column(
        table,
        sa.Column(
            "tool_arguments",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        table,
        sa.Column("execution_mode", sa.String(length=16), server_default="shadow", nullable=False),
    )
    op.add_column(
        table,
        sa.Column("canary_percentage", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(f"ck_{prefix}_mode", table, "execution_mode IN ('shadow', 'live')")
    op.create_check_constraint(f"ck_{prefix}_canary", table, "canary_percentage BETWEEN 0 AND 100")


def upgrade() -> None:
    _add_source_execution_columns("agent_execution_schedules", "agent_execution_schedule")
    _add_source_execution_columns("agent_event_triggers", "agent_event_trigger")
    op.drop_constraint(
        "ck_agent_runtime_dispatch_status", "agent_runtime_dispatches", type_="check"
    )
    op.create_check_constraint(
        "ck_agent_runtime_dispatch_status",
        "agent_runtime_dispatches",
        "status IN ('ready', 'blocked', 'processing', 'awaiting_approval', "
        "'simulated', 'completed', 'failed')",
    )
    op.add_column(
        "agent_runtime_dispatches", sa.Column("error_code", sa.String(length=120), nullable=True)
    )
    op.add_column(
        "agent_runtime_dispatches",
        sa.Column(
            "tool_arguments",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "agent_runtime_dispatches",
        sa.Column("execution_mode", sa.String(length=16), server_default="shadow", nullable=False),
    )
    op.add_column(
        "agent_runtime_dispatches",
        sa.Column("canary_percentage", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "agent_runtime_dispatches", sa.Column("agent_run_id", postgresql.UUID(), nullable=True)
    )
    op.add_column(
        "agent_runtime_dispatches",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "agent_runtime_dispatches",
        sa.Column("reserved_microunits", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "agent_runtime_dispatches",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_runtime_dispatches",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_runtime_dispatch_run",
        "agent_runtime_dispatches",
        "agent_runs",
        ["agent_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_agent_runtime_dispatch_run", "agent_runtime_dispatches", ["agent_run_id"]
    )
    op.create_index(
        "ix_agent_runtime_dispatches_agent_run_id",
        "agent_runtime_dispatches",
        ["agent_run_id"],
    )
    op.create_index(
        "ix_agent_runtime_dispatches_error_code", "agent_runtime_dispatches", ["error_code"]
    )
    op.create_index(
        "ix_agent_runtime_dispatches_execution_mode",
        "agent_runtime_dispatches",
        ["execution_mode"],
    )
    op.create_index(
        "ix_agent_runtime_dispatches_started_at", "agent_runtime_dispatches", ["started_at"]
    )
    op.create_index(
        "ix_agent_runtime_dispatches_finished_at", "agent_runtime_dispatches", ["finished_at"]
    )
    op.create_check_constraint(
        "ck_agent_runtime_dispatch_mode",
        "agent_runtime_dispatches",
        "execution_mode IN ('shadow', 'live')",
    )
    op.create_check_constraint(
        "ck_agent_runtime_dispatch_canary",
        "agent_runtime_dispatches",
        "canary_percentage BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_agent_runtime_dispatch_counters",
        "agent_runtime_dispatches",
        "attempt_count >= 0 AND reserved_microunits >= 0",
    )
    op.drop_constraint("ck_agent_run_steps_type", "agent_run_steps", type_="check")
    op.create_check_constraint(
        "ck_agent_run_steps_type",
        "agent_run_steps",
        "step_type IN ('provider', 'runtime', 'tool')",
    )


def _drop_source_execution_columns(table: str, prefix: str) -> None:
    op.drop_constraint(f"ck_{prefix}_canary", table, type_="check")
    op.drop_constraint(f"ck_{prefix}_mode", table, type_="check")
    op.drop_column(table, "canary_percentage")
    op.drop_column(table, "execution_mode")
    op.drop_column(table, "tool_arguments")


def downgrade() -> None:
    op.execute(
        "UPDATE agent_runtime_dispatches SET status = 'blocked', "
        "reason_code = 'rollback_required' WHERE status NOT IN ('ready', 'blocked')"
    )
    op.execute("DELETE FROM agent_run_steps WHERE step_type = 'runtime'")
    op.drop_constraint("ck_agent_run_steps_type", "agent_run_steps", type_="check")
    op.create_check_constraint(
        "ck_agent_run_steps_type", "agent_run_steps", "step_type IN ('provider', 'tool')"
    )
    op.drop_constraint(
        "ck_agent_runtime_dispatch_counters", "agent_runtime_dispatches", type_="check"
    )
    op.drop_constraint(
        "ck_agent_runtime_dispatch_canary", "agent_runtime_dispatches", type_="check"
    )
    op.drop_constraint("ck_agent_runtime_dispatch_mode", "agent_runtime_dispatches", type_="check")
    op.drop_index("ix_agent_runtime_dispatches_finished_at", table_name="agent_runtime_dispatches")
    op.drop_index("ix_agent_runtime_dispatches_started_at", table_name="agent_runtime_dispatches")
    op.drop_index(
        "ix_agent_runtime_dispatches_execution_mode", table_name="agent_runtime_dispatches"
    )
    op.drop_index("ix_agent_runtime_dispatches_error_code", table_name="agent_runtime_dispatches")
    op.drop_index("ix_agent_runtime_dispatches_agent_run_id", table_name="agent_runtime_dispatches")
    op.drop_constraint("uq_agent_runtime_dispatch_run", "agent_runtime_dispatches", type_="unique")
    op.drop_constraint(
        "fk_agent_runtime_dispatch_run", "agent_runtime_dispatches", type_="foreignkey"
    )
    for column in (
        "finished_at",
        "started_at",
        "reserved_microunits",
        "attempt_count",
        "agent_run_id",
        "canary_percentage",
        "execution_mode",
        "tool_arguments",
        "error_code",
    ):
        op.drop_column("agent_runtime_dispatches", column)
    op.drop_constraint(
        "ck_agent_runtime_dispatch_status", "agent_runtime_dispatches", type_="check"
    )
    op.create_check_constraint(
        "ck_agent_runtime_dispatch_status",
        "agent_runtime_dispatches",
        "status IN ('ready', 'blocked')",
    )
    _drop_source_execution_columns("agent_event_triggers", "agent_event_trigger")
    _drop_source_execution_columns("agent_execution_schedules", "agent_execution_schedule")
