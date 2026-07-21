"""Add incident review queue and temporary quarantine.

Revision ID: 20260721_0054
Revises: 20260721_0053
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0054"
down_revision: str | None = "20260721_0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    incidents = "agent_task_memory_access_incidents"
    op.add_column(
        incidents,
        sa.Column("quarantine_minutes", sa.Integer(), server_default="60", nullable=False),
    )
    op.add_column(
        incidents,
        sa.Column("quarantine_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        incidents,
        sa.Column("review_status", sa.String(16), server_default="pending", nullable=False),
    )
    op.add_column(incidents, sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True))
    op.add_column(incidents, sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        sa.text(
            "UPDATE agent_task_memory_access_incidents "
            "SET quarantine_until = created_at + interval '60 minutes'"
        )
    )
    op.alter_column(incidents, "quarantine_until", nullable=False)
    op.create_check_constraint(
        "ck_agent_task_memory_incident_quarantine",
        incidents,
        "quarantine_minutes BETWEEN 5 AND 1440 AND quarantine_until >= created_at",
    )
    op.create_check_constraint(
        "ck_agent_task_memory_incident_review_status",
        incidents,
        "review_status IN ('pending', 'confirmed', 'dismissed')",
    )
    op.create_check_constraint(
        "ck_agent_task_memory_incident_review",
        incidents,
        "(review_status = 'pending' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL) OR "
        "(review_status IN ('confirmed', 'dismissed') AND reviewed_by_user_id IS NOT NULL "
        "AND reviewed_at IS NOT NULL AND reviewed_by_user_id <> triggered_by_user_id)",
    )
    op.create_foreign_key(
        "fk_task_memory_incident_reviewed_by",
        incidents,
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    for column in ("quarantine_until", "review_status", "reviewed_by_user_id"):
        op.create_index(f"ix_{incidents}_{column}", incidents, [column])


def downgrade() -> None:
    incidents = "agent_task_memory_access_incidents"
    for column in reversed(("quarantine_until", "review_status", "reviewed_by_user_id")):
        op.drop_index(f"ix_{incidents}_{column}", table_name=incidents)
    op.drop_constraint("fk_task_memory_incident_reviewed_by", incidents, type_="foreignkey")
    op.drop_constraint("ck_agent_task_memory_incident_review", incidents, type_="check")
    op.drop_constraint("ck_agent_task_memory_incident_review_status", incidents, type_="check")
    op.drop_constraint("ck_agent_task_memory_incident_quarantine", incidents, type_="check")
    op.drop_column(incidents, "reviewed_at")
    op.drop_column(incidents, "reviewed_by_user_id")
    op.drop_column(incidents, "review_status")
    op.drop_column(incidents, "quarantine_until")
    op.drop_column(incidents, "quarantine_minutes")
