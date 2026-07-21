"""Add explicit minimized access contracts for shared task memory.

Revision ID: 20260721_0049
Revises: 20260721_0048
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0049"
down_revision: str | None = "20260721_0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_task_memory_access_grants",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("task_delegation_id", sa.Uuid(), nullable=False),
        sa.Column("owner_agent_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_agent_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column(
            "allowed_classifications", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("max_entries", sa.Integer(), nullable=False),
        sa.Column("max_content_characters", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("revoked_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("revocation_reason_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "owner_agent_id <> recipient_agent_id",
            name="ck_agent_task_memory_access_distinct_agents",
        ),
        sa.CheckConstraint(
            "purpose IN ('coordination', 'review', 'handoff')",
            name="ck_agent_task_memory_access_purpose",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked', 'expired')",
            name="ck_agent_task_memory_access_status",
        ),
        sa.CheckConstraint(
            "max_entries BETWEEN 1 AND 5",
            name="ck_agent_task_memory_access_entries",
        ),
        sa.CheckConstraint(
            "max_content_characters BETWEEN 64 AND 2000",
            name="ck_agent_task_memory_access_characters",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_agent_task_memory_access_expiration",
        ),
        sa.CheckConstraint(
            "(status IN ('active', 'expired') AND revoked_by_user_id IS NULL "
            "AND revoked_at IS NULL AND revocation_reason_fingerprint IS NULL) OR "
            "(status = 'revoked' AND revoked_by_user_id IS NOT NULL "
            "AND revoked_at IS NOT NULL AND revocation_reason_fingerprint IS NOT NULL)",
            name="ck_agent_task_memory_access_revocation",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["task_delegation_id"], ["agent_delegations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["owner_agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "idempotency_key",
            name="uq_agent_task_memory_access_idempotency",
        ),
    )
    for column in (
        "company_id",
        "task_delegation_id",
        "owner_agent_id",
        "recipient_agent_id",
        "purpose",
        "status",
        "idempotency_key",
        "granted_by_user_id",
        "revoked_by_user_id",
        "expires_at",
        "created_at",
    ):
        op.create_index(
            f"ix_agent_task_memory_access_{column}",
            "agent_task_memory_access_grants",
            [column],
        )


def downgrade() -> None:
    op.drop_table("agent_task_memory_access_grants")
