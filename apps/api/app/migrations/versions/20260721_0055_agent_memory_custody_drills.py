"""Add incident quorum, report custody chain and response exercises.

Revision ID: 20260721_0055
Revises: 20260721_0054
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0055"
down_revision: str | None = "20260721_0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _indexes(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    incidents = "agent_task_memory_access_incidents"
    op.add_column(
        incidents, sa.Column("severity", sa.String(16), server_default="high", nullable=False)
    )
    op.add_column(
        incidents,
        sa.Column("required_review_quorum", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        incidents, sa.Column("review_count", sa.Integer(), server_default="0", nullable=False)
    )
    op.execute(
        sa.text(
            "UPDATE agent_task_memory_access_incidents SET review_count = 1 "
            "WHERE review_status IN ('confirmed', 'dismissed')"
        )
    )
    op.create_check_constraint(
        "ck_agent_task_memory_incident_severity",
        incidents,
        "severity IN ('low', 'medium', 'high', 'critical')",
    )
    op.create_check_constraint(
        "ck_agent_task_memory_incident_quorum",
        incidents,
        "required_review_quorum BETWEEN 1 AND 5 "
        "AND (severity <> 'critical' OR required_review_quorum >= 2) AND review_count >= 0",
    )

    reviews = "agent_task_memory_incident_reviews"
    op.create_table(
        reviews,
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "decision IN ('confirmed', 'dismissed')",
            name="ck_agent_task_memory_incident_review_decision",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["agent_task_memory_access_incidents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "incident_id", "reviewer_user_id", name="uq_agent_task_memory_incident_reviewer"
        ),
    )
    _indexes(
        reviews,
        ("company_id", "incident_id", "agent_id", "reviewer_user_id", "decision", "created_at"),
    )

    reports = "agent_memory_risk_report_records"
    op.create_table(
        reports,
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("previous_signature", sa.String(64), nullable=True),
        sa.Column("generated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("sequence >= 1", name="ck_agent_memory_risk_report_sequence"),
        sa.CheckConstraint(
            "char_length(signature) = 64 AND "
            "(previous_signature IS NULL OR char_length(previous_signature) = 64)",
            name="ck_agent_memory_risk_report_signatures",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "agent_id", "sequence", name="uq_agent_memory_risk_report_sequence"
        ),
    )
    _indexes(
        reports,
        ("company_id", "agent_id", "signature", "generated_by_user_id", "created_at"),
    )

    exercises = "agent_memory_response_exercises"
    op.create_table(
        exercises,
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("scenario", sa.String(16), server_default="full", nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("checks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("scenario = 'full'", name="ck_agent_memory_exercise_scenario"),
        sa.CheckConstraint(
            "status IN ('passed', 'failed')", name="ck_agent_memory_exercise_status"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(exercises, ("company_id", "agent_id", "status", "requested_by_user_id", "created_at"))


def downgrade() -> None:
    for table, columns in (
        (
            "agent_memory_response_exercises",
            ("company_id", "agent_id", "status", "requested_by_user_id", "created_at"),
        ),
        (
            "agent_memory_risk_report_records",
            ("company_id", "agent_id", "signature", "generated_by_user_id", "created_at"),
        ),
        (
            "agent_task_memory_incident_reviews",
            ("company_id", "incident_id", "agent_id", "reviewer_user_id", "decision", "created_at"),
        ),
    ):
        for column in reversed(columns):
            op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_table(table)
    incidents = "agent_task_memory_access_incidents"
    op.drop_constraint("ck_agent_task_memory_incident_quorum", incidents, type_="check")
    op.drop_constraint("ck_agent_task_memory_incident_severity", incidents, type_="check")
    op.drop_column(incidents, "review_count")
    op.drop_column(incidents, "required_review_quorum")
    op.drop_column(incidents, "severity")
