"""Add versioned agent approval policies.

Revision ID: 20260721_0039
Revises: 20260721_0038
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0039"
down_revision: str | None = "20260721_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_approval_policy_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_key", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("effect", sa.String(length=24), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("tool_key", sa.String(length=160), nullable=True),
        sa.Column("amount_field", sa.String(length=160), nullable=True),
        sa.Column("min_amount_microunits", sa.Integer(), nullable=True),
        sa.Column("max_amount_microunits", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column(
            "context_conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("approval_ttl_minutes", sa.Integer(), server_default="30", nullable=False),
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'retired')",
            name="ck_agent_approval_policy_status",
        ),
        sa.CheckConstraint(
            "effect IN ('allow', 'require_approval', 'deny')",
            name="ck_agent_approval_policy_effect",
        ),
        sa.CheckConstraint("priority BETWEEN 0 AND 1000", name="ck_agent_approval_policy_priority"),
        sa.CheckConstraint(
            "approval_ttl_minutes BETWEEN 5 AND 10080",
            name="ck_agent_approval_policy_ttl",
        ),
        sa.CheckConstraint(
            "min_amount_microunits IS NULL OR min_amount_microunits >= 0",
            name="ck_agent_approval_policy_min_amount",
        ),
        sa.CheckConstraint(
            "max_amount_microunits IS NULL OR max_amount_microunits >= 0",
            name="ck_agent_approval_policy_max_amount",
        ),
        sa.CheckConstraint(
            "min_amount_microunits IS NULL OR max_amount_microunits IS NULL "
            "OR max_amount_microunits >= min_amount_microunits",
            name="ck_agent_approval_policy_amount_range",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "agent_id",
            "policy_key",
            "version",
            name="uq_agent_approval_policy_version",
        ),
    )
    for column in (
        "company_id",
        "agent_id",
        "policy_key",
        "status",
        "effect",
        "tool_key",
        "assigned_user_id",
        "created_by_user_id",
        "created_at",
    ):
        op.create_index(
            f"ix_agent_approval_policy_versions_{column}",
            "agent_approval_policy_versions",
            [column],
        )
    op.add_column(
        "agent_delegation_approvals",
        sa.Column("policy_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_delegation_approvals_policy_version_id",
        "agent_delegation_approvals",
        "agent_approval_policy_versions",
        ["policy_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_agent_delegation_approvals_policy_version_id",
        "agent_delegation_approvals",
        ["policy_version_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_delegation_approvals_policy_version_id",
        table_name="agent_delegation_approvals",
    )
    op.drop_constraint(
        "fk_agent_delegation_approvals_policy_version_id",
        "agent_delegation_approvals",
        type_="foreignkey",
    )
    op.drop_column("agent_delegation_approvals", "policy_version_id")
    for column in reversed(
        (
            "company_id",
            "agent_id",
            "policy_key",
            "status",
            "effect",
            "tool_key",
            "assigned_user_id",
            "created_by_user_id",
            "created_at",
        )
    ):
        op.drop_index(
            f"ix_agent_approval_policy_versions_{column}",
            table_name="agent_approval_policy_versions",
        )
    op.drop_table("agent_approval_policy_versions")
