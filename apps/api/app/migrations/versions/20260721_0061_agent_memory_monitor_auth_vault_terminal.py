"""Authenticate memory monitoring and coordinate terminal key recovery.

Revision ID: 20260721_0061
Revises: 20260721_0060
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0061"
down_revision: str | None = "20260721_0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "agent_memory_reencryption_jobs"
    op.drop_constraint("ck_agent_memory_reencryption_job_status", table, type_="check")
    op.create_check_constraint(
        "ck_agent_memory_reencryption_job_status",
        table,
        "status IN ('pending', 'running', 'completed', 'failed', 'closed')",
    )
    op.add_column(
        table,
        sa.Column(
            "key_provider", sa.String(length=24), server_default="environment", nullable=False
        ),
    )
    op.add_column(
        table,
        sa.Column(
            "target_key_reference_fingerprint",
            sa.String(length=64),
            server_default="0" * 64,
            nullable=False,
        ),
    )
    op.add_column(table, sa.Column("closure_code", sa.String(length=32), nullable=True))
    op.add_column(
        table,
        sa.Column("closure_reason_fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column(table, sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        table,
        sa.Column(
            "closed_by_user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_agent_memory_reencryption_job_key_provider",
        table,
        "key_provider IN ('environment', 'external') "
        "AND char_length(target_key_reference_fingerprint) = 64",
    )
    op.create_check_constraint(
        "ck_agent_memory_reencryption_job_closure",
        table,
        "(status = 'closed' AND closure_code IS NOT NULL "
        "AND char_length(closure_reason_fingerprint) = 64 "
        "AND closed_at IS NOT NULL AND closed_by_user_id IS NOT NULL) OR "
        "(status <> 'closed' AND closure_code IS NULL "
        "AND closure_reason_fingerprint IS NULL "
        "AND closed_at IS NULL AND closed_by_user_id IS NULL)",
    )
    op.create_index(f"ix_{table}_closed_by_user_id", table, ["closed_by_user_id"])


def downgrade() -> None:
    table = "agent_memory_reencryption_jobs"
    op.drop_index(f"ix_{table}_closed_by_user_id", table_name=table)
    op.drop_constraint("ck_agent_memory_reencryption_job_closure", table, type_="check")
    op.drop_constraint("ck_agent_memory_reencryption_job_key_provider", table, type_="check")
    op.drop_column(table, "closed_by_user_id")
    op.drop_column(table, "closed_at")
    op.drop_column(table, "closure_reason_fingerprint")
    op.drop_column(table, "closure_code")
    op.drop_column(table, "target_key_reference_fingerprint")
    op.drop_column(table, "key_provider")
    op.drop_constraint("ck_agent_memory_reencryption_job_status", table, type_="check")
    op.create_check_constraint(
        "ck_agent_memory_reencryption_job_status",
        table,
        "status IN ('pending', 'running', 'completed', 'failed')",
    )
