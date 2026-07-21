"""Add retry budgets and assisted recovery state for memory encryption jobs.

Revision ID: 20260721_0060
Revises: 20260721_0059
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0060"
down_revision: str | None = "20260721_0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "agent_memory_reencryption_jobs"
    op.add_column(
        table,
        sa.Column("max_retry_attempts", sa.Integer(), server_default="3", nullable=False),
    )
    op.execute(
        "UPDATE agent_memory_reencryption_jobs "
        "SET max_retry_attempts = GREATEST(3, retry_count)"
    )
    op.add_column(
        table,
        sa.Column(
            "recovery_status",
            sa.String(length=24),
            server_default="not_assessed",
            nullable=False,
        ),
    )
    op.add_column(
        table,
        sa.Column("last_recovery_assessment_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        table,
        sa.Column(
            "recovery_assessed_by_user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_agent_memory_reencryption_job_retry_budget",
        table,
        "max_retry_attempts BETWEEN 1 AND 100 AND retry_count <= max_retry_attempts",
    )
    op.create_check_constraint(
        "ck_agent_memory_reencryption_job_recovery",
        table,
        "(recovery_status = 'not_assessed' "
        "AND last_recovery_assessment_at IS NULL "
        "AND recovery_assessed_by_user_id IS NULL) OR "
        "(recovery_status IN ('ready', 'blocked') "
        "AND last_recovery_assessment_at IS NOT NULL "
        "AND recovery_assessed_by_user_id IS NOT NULL)",
    )
    op.create_index(f"ix_{table}_recovery_status", table, ["recovery_status"])
    op.create_index(
        f"ix_{table}_recovery_assessed_by_user_id",
        table,
        ["recovery_assessed_by_user_id"],
    )


def downgrade() -> None:
    table = "agent_memory_reencryption_jobs"
    op.drop_index(f"ix_{table}_recovery_assessed_by_user_id", table_name=table)
    op.drop_index(f"ix_{table}_recovery_status", table_name=table)
    op.drop_constraint("ck_agent_memory_reencryption_job_recovery", table, type_="check")
    op.drop_constraint("ck_agent_memory_reencryption_job_retry_budget", table, type_="check")
    op.drop_column(table, "recovery_assessed_by_user_id")
    op.drop_column(table, "last_recovery_assessment_at")
    op.drop_column(table, "recovery_status")
    op.drop_column(table, "max_retry_attempts")
