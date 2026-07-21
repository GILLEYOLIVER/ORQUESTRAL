"""Add memory re-encryption jobs, incident assignees and scheduler metrics.

Revision ID: 20260721_0058
Revises: 20260721_0057
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0058"
down_revision: str | None = "20260721_0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_task_memory_incident_assignees",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("responsible_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["agent_task_memory_access_incidents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["responsible_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "incident_id",
            "responsible_user_id",
            name="uq_agent_task_memory_incident_assignee",
        ),
    )
    assignee_table = "agent_task_memory_incident_assignees"
    for column in (
        "company_id",
        "incident_id",
        "agent_id",
        "responsible_user_id",
        "assigned_by_user_id",
        "created_at",
    ):
        op.create_index(f"ix_{assignee_table}_{column}", assignee_table, [column])

    exercise_table = "agent_memory_response_exercises"
    op.add_column(
        exercise_table,
        sa.Column("source", sa.String(length=24), server_default="manual", nullable=False),
    )
    op.add_column(
        exercise_table,
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "ck_agent_memory_exercise_source",
        exercise_table,
        "source IN ('manual', 'manual_schedule', 'worker_schedule')",
    )
    op.create_check_constraint(
        "ck_agent_memory_exercise_duration", exercise_table, "duration_ms >= 0"
    )

    job_table = "agent_memory_reencryption_jobs"
    op.create_table(
        job_table,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("target_master_key_id", sa.String(length=64), nullable=False),
        sa.Column("batch_size", sa.Integer(), server_default="100", nullable=False),
        sa.Column("total_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("scanned_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rotated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("checkpoint_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checkpoint_memory_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_agent_memory_reencryption_job_status",
        ),
        sa.CheckConstraint(
            "batch_size BETWEEN 1 AND 500",
            name="ck_agent_memory_reencryption_job_batch_size",
        ),
        sa.CheckConstraint(
            "total_count >= 0 AND scanned_count >= 0 AND rotated_count >= 0 "
            "AND failed_count >= 0 AND scanned_count <= total_count "
            "AND rotated_count + failed_count <= scanned_count",
            name="ck_agent_memory_reencryption_job_counts",
        ),
        sa.CheckConstraint(
            "(checkpoint_created_at IS NULL AND checkpoint_memory_id IS NULL) OR "
            "(checkpoint_created_at IS NOT NULL AND checkpoint_memory_id IS NOT NULL)",
            name="ck_agent_memory_reencryption_job_checkpoint",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "agent_id",
        "status",
        "target_master_key_id",
        "requested_by_user_id",
        "created_at",
    ):
        op.create_index(f"ix_{job_table}_{column}", job_table, [column])
    op.create_index(
        "uq_agent_memory_reencryption_job_active",
        job_table,
        ["company_id", "agent_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    job_table = "agent_memory_reencryption_jobs"
    op.drop_index("uq_agent_memory_reencryption_job_active", table_name=job_table)
    for column in reversed(
        (
            "company_id",
            "agent_id",
            "status",
            "target_master_key_id",
            "requested_by_user_id",
            "created_at",
        )
    ):
        op.drop_index(f"ix_{job_table}_{column}", table_name=job_table)
    op.drop_table(job_table)

    exercise_table = "agent_memory_response_exercises"
    op.drop_constraint("ck_agent_memory_exercise_duration", exercise_table, type_="check")
    op.drop_constraint("ck_agent_memory_exercise_source", exercise_table, type_="check")
    op.drop_column(exercise_table, "duration_ms")
    op.drop_column(exercise_table, "source")

    assignee_table = "agent_task_memory_incident_assignees"
    for column in reversed(
        (
            "company_id",
            "incident_id",
            "agent_id",
            "responsible_user_id",
            "assigned_by_user_id",
            "created_at",
        )
    ):
        op.drop_index(f"ix_{assignee_table}_{column}", table_name=assignee_table)
    op.drop_table(assignee_table)
