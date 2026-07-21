"""Add memory recovery controls, reassignment support and scheduler SLOs.

Revision ID: 20260721_0059
Revises: 20260721_0058
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0059"
down_revision: str | None = "20260721_0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    incident_table = "agent_task_memory_access_incidents"
    op.add_column(
        incident_table,
        sa.Column("request_fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_agent_task_memory_incident_request_fingerprint",
        incident_table,
        "request_fingerprint IS NULL OR char_length(request_fingerprint) = 64",
    )

    schedule_table = "agent_memory_exercise_schedules"
    op.add_column(
        schedule_table,
        sa.Column("heartbeat_slo_minutes", sa.Integer(), server_default="15", nullable=False),
    )
    op.add_column(
        schedule_table,
        sa.Column("last_worker_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        schedule_table,
        sa.Column("last_slo_alert_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        schedule_table,
        sa.Column("slo_breach_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "ck_agent_memory_exercise_schedule_slo",
        schedule_table,
        "heartbeat_slo_minutes BETWEEN 5 AND 1440 AND slo_breach_count >= 0",
    )
    op.create_index(
        f"ix_{schedule_table}_last_worker_heartbeat_at",
        schedule_table,
        ["last_worker_heartbeat_at"],
    )

    job_table = "agent_memory_reencryption_jobs"
    op.add_column(
        job_table,
        sa.Column("snapshot_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        job_table,
        sa.Column("snapshot_memory_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        job_table,
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        job_table,
        sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        job_table,
        sa.Column("retry_reason_fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_agent_memory_reencryption_job_snapshot",
        job_table,
        "(snapshot_created_at IS NULL AND snapshot_memory_id IS NULL) OR "
        "(snapshot_created_at IS NOT NULL AND snapshot_memory_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_agent_memory_reencryption_job_retry",
        job_table,
        "(retry_count = 0 AND last_retry_at IS NULL AND retry_reason_fingerprint IS NULL) OR "
        "(retry_count > 0 AND last_retry_at IS NOT NULL "
        "AND char_length(retry_reason_fingerprint) = 64)",
    )


def downgrade() -> None:
    job_table = "agent_memory_reencryption_jobs"
    op.drop_constraint("ck_agent_memory_reencryption_job_retry", job_table, type_="check")
    op.drop_constraint("ck_agent_memory_reencryption_job_snapshot", job_table, type_="check")
    op.drop_column(job_table, "retry_reason_fingerprint")
    op.drop_column(job_table, "last_retry_at")
    op.drop_column(job_table, "retry_count")
    op.drop_column(job_table, "snapshot_memory_id")
    op.drop_column(job_table, "snapshot_created_at")

    schedule_table = "agent_memory_exercise_schedules"
    op.drop_index(f"ix_{schedule_table}_last_worker_heartbeat_at", table_name=schedule_table)
    op.drop_constraint("ck_agent_memory_exercise_schedule_slo", schedule_table, type_="check")
    op.drop_column(schedule_table, "slo_breach_count")
    op.drop_column(schedule_table, "last_slo_alert_at")
    op.drop_column(schedule_table, "last_worker_heartbeat_at")
    op.drop_column(schedule_table, "heartbeat_slo_minutes")

    incident_table = "agent_task_memory_access_incidents"
    op.drop_constraint(
        "ck_agent_task_memory_incident_request_fingerprint",
        incident_table,
        type_="check",
    )
    op.drop_column(incident_table, "request_fingerprint")
