"""Add independently approved reencryption hold renewals.

Revision ID: 20260721_0067
Revises: 20260721_0066
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0067"
down_revision: str | None = "20260721_0066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "agent_memory_reencryption_legal_hold_renewals"
    op.create_table(
        table,
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_memory_reencryption_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "hold_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_memory_reencryption_legal_holds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("extension_days", sa.Integer(), nullable=False),
        sa.Column("legal_reference_fingerprint", sa.String(64), nullable=False),
        sa.Column("proposed_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column(
            "requested_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "decided_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_amr_legal_hold_renewal_status",
        ),
        sa.CheckConstraint(
            "extension_days BETWEEN 1 AND 3650 AND proposed_expires_at > created_at",
            name="ck_amr_legal_hold_renewal_extension",
        ),
        sa.CheckConstraint(
            "decided_by_user_id IS NULL OR decided_by_user_id <> requested_by_user_id",
            name="ck_amr_legal_hold_renewal_separation",
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND decided_by_user_id IS NULL AND decided_at IS NULL) OR "
            "(status IN ('approved', 'rejected') AND decided_by_user_id IS NOT NULL "
            "AND decided_at IS NOT NULL)",
            name="ck_amr_legal_hold_renewal_decision",
        ),
    )
    for column in (
        "company_id",
        "agent_id",
        "job_id",
        "hold_id",
        "status",
        "requested_by_user_id",
        "decided_by_user_id",
        "created_at",
    ):
        op.create_index(f"ix_amr_hold_renewals_{column}", table, [column])
    op.create_index(
        "uq_amr_legal_hold_renewal_pending",
        table,
        ["company_id", "hold_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_table("agent_memory_reencryption_legal_hold_renewals")
