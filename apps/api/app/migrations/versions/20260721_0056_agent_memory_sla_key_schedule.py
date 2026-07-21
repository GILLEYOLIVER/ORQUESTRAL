"""Add incident SLA, signing key versions and exercise schedules.

Revision ID: 20260721_0056
Revises: 20260721_0055
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0056"
down_revision: str | None = "20260721_0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _indexes(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    incidents = "agent_task_memory_access_incidents"
    op.add_column(
        incidents,
        sa.Column("review_sla_minutes", sa.Integer(), server_default="60", nullable=False),
    )
    op.add_column(incidents, sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        incidents,
        sa.Column("escalation_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(incidents, sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        sa.text(
            "UPDATE agent_task_memory_access_incidents "
            "SET review_due_at = created_at + interval '60 minutes'"
        )
    )
    op.alter_column(incidents, "review_due_at", nullable=False)
    op.create_check_constraint(
        "ck_agent_task_memory_incident_sla",
        incidents,
        "review_sla_minutes BETWEEN 5 AND 1440 AND review_due_at > created_at "
        "AND escalation_count >= 0",
    )
    _indexes(incidents, ("review_due_at", "escalated_at"))

    reports = "agent_memory_risk_report_records"
    op.add_column(
        reports,
        sa.Column("signature_key_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_check_constraint(
        "ck_agent_memory_risk_report_key_version", reports, "signature_key_version >= 1"
    )

    keys = "agent_memory_risk_signing_key_versions"
    op.create_table(
        keys,
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("activated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("version >= 1", name="ck_agent_memory_risk_signing_key_version"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["activated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "agent_id", "version", name="uq_agent_memory_risk_signing_key_version"
        ),
    )
    _indexes(keys, ("company_id", "agent_id", "activated_by_user_id", "created_at"))

    schedules = "agent_memory_exercise_schedules"
    op.create_table(
        schedules,
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("cadence_hours", sa.Integer(), server_default="168", nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "cadence_hours BETWEEN 1 AND 720",
            name="ck_agent_memory_exercise_schedule_cadence",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", name="uq_agent_memory_exercise_schedule_agent"),
    )
    _indexes(schedules, ("company_id", "agent_id", "next_run_at", "updated_by_user_id"))


def downgrade() -> None:
    for table, columns in (
        (
            "agent_memory_exercise_schedules",
            ("company_id", "agent_id", "next_run_at", "updated_by_user_id"),
        ),
        (
            "agent_memory_risk_signing_key_versions",
            ("company_id", "agent_id", "activated_by_user_id", "created_at"),
        ),
    ):
        for column in reversed(columns):
            op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_table(table)
    reports = "agent_memory_risk_report_records"
    op.drop_constraint("ck_agent_memory_risk_report_key_version", reports, type_="check")
    op.drop_column(reports, "signature_key_version")
    incidents = "agent_task_memory_access_incidents"
    for column in reversed(("review_due_at", "escalated_at")):
        op.drop_index(f"ix_{incidents}_{column}", table_name=incidents)
    op.drop_constraint("ck_agent_task_memory_incident_sla", incidents, type_="check")
    op.drop_column(incidents, "escalated_at")
    op.drop_column(incidents, "escalation_count")
    op.drop_column(incidents, "review_due_at")
    op.drop_column(incidents, "review_sla_minutes")
