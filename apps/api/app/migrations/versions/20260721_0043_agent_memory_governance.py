"""Add governed and encrypted agent memories.

Revision ID: 20260721_0043
Revises: 20260721_0042
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0043"
down_revision: str | None = "20260721_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_memory_policies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("default_retention_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column("max_retention_days", sa.Integer(), server_default="365", nullable=False),
        sa.Column(
            "allowed_scopes",
            postgresql.JSONB(),
            server_default=sa.text('\'["conversation","task","operational"]\'::jsonb'),
            nullable=False,
        ),
        sa.Column(
            "allowed_classifications",
            postgresql.JSONB(),
            server_default=sa.text('\'["public","internal"]\'::jsonb'),
            nullable=False,
        ),
        sa.Column(
            "require_consent_for_user_scope", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "default_retention_days BETWEEN 1 AND 3650",
            name="ck_agent_memory_policy_default_retention",
        ),
        sa.CheckConstraint(
            "max_retention_days BETWEEN default_retention_days AND 3650",
            name="ck_agent_memory_policy_max_retention",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", name="uq_agent_memory_policies_agent"),
    )
    for column in ("company_id", "agent_id", "updated_by_user_id"):
        op.create_index(f"ix_agent_memory_policies_{column}", "agent_memory_policies", [column])
    op.create_table(
        "agent_memory_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(length=24), nullable=False),
        sa.Column("classification", sa.String(length=24), nullable=False),
        sa.Column("encrypted_content", sa.LargeBinary(), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=24), server_default="manual", nullable=False),
        sa.Column("source_id", sa.String(length=160), nullable=True),
        sa.Column("consent_reference", sa.String(length=160), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "scope IN ('conversation', 'task', 'user', 'company', 'operational')",
            name="ck_agent_memory_scope",
        ),
        sa.CheckConstraint(
            "classification IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_agent_memory_classification",
        ),
        sa.CheckConstraint(
            "source_type IN ('manual', 'conversation', 'task', 'tool')",
            name="ck_agent_memory_source_type",
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_agent_memory_expiration"),
        sa.CheckConstraint(
            "scope <> 'user' OR consent_reference IS NOT NULL", name="ck_agent_memory_user_consent"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "agent_id", "content_fingerprint", name="uq_agent_memory_content"
        ),
    )
    for column in (
        "company_id",
        "agent_id",
        "created_by_user_id",
        "scope",
        "classification",
        "content_fingerprint",
        "expires_at",
        "created_at",
    ):
        op.create_index(f"ix_agent_memory_entries_{column}", "agent_memory_entries", [column])


def downgrade() -> None:
    op.drop_table("agent_memory_entries")
    op.drop_table("agent_memory_policies")
