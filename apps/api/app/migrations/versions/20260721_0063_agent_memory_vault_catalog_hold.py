"""Add governed legal hold for terminal memory re-encryption jobs.

Revision ID: 20260721_0063
Revises: 20260721_0062
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0063"
down_revision: str | None = "20260721_0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "agent_memory_reencryption_legal_holds"
    op.create_table(
        table,
        sa.Column(
            "id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("company_id", postgresql.UUID(), nullable=False),
        sa.Column("agent_id", postgresql.UUID(), nullable=False),
        sa.Column("job_id", postgresql.UUID(), nullable=False),
        sa.Column("reason_code", sa.String(32), nullable=False),
        sa.Column("legal_reference_fingerprint", sa.String(64), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(), nullable=False),
        sa.Column("decided_by_user_id", postgresql.UUID(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_agent_memory_reencryption_legal_hold_status",
        ),
        sa.CheckConstraint(
            "reason_code IN ('legal_claim', 'regulatory_request', 'audit_preservation')",
            name="ck_agent_memory_reencryption_legal_hold_reason",
        ),
        sa.CheckConstraint(
            "retention_days BETWEEN 1 AND 3650 AND expires_at > created_at",
            name="ck_agent_memory_reencryption_legal_hold_retention",
        ),
        sa.CheckConstraint(
            "decided_by_user_id IS NULL OR decided_by_user_id <> requested_by_user_id",
            name="ck_agent_memory_reencryption_legal_hold_separation",
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND decided_by_user_id IS NULL AND decided_at IS NULL) OR "
            "(status IN ('approved', 'rejected') AND decided_by_user_id IS NOT NULL "
            "AND decided_at IS NOT NULL)",
            name="ck_agent_memory_reencryption_legal_hold_decision",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["job_id"], ["agent_memory_reencryption_jobs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "agent_id",
        "job_id",
        "reason_code",
        "status",
        "requested_by_user_id",
        "decided_by_user_id",
        "expires_at",
        "created_at",
    ):
        op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index(
        "ix_amr_legal_hold_reference",
        table,
        ["legal_reference_fingerprint"],
    )
    op.create_index(
        "uq_agent_memory_reencryption_legal_hold_active",
        table,
        ["company_id", "job_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'approved')"),
    )


def downgrade() -> None:
    op.drop_table("agent_memory_reencryption_legal_holds")
