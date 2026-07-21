"""Create enterprise policy decision ledger.

Revision ID: 20260721_0029
Revises: 20260721_0028
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0029"
down_revision: str | None = "20260721_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_type", sa.String(length=120), nullable=False),
        sa.Column("resource_id", sa.String(length=160), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("required_permission", sa.String(length=160), nullable=True),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("requested_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("allowed_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("denied_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risk_level", sa.String(length=24), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policy_decisions_action", "policy_decisions", ["action"])
    op.create_index("ix_policy_decisions_company_id", "policy_decisions", ["company_id"])
    op.create_index(
        "ix_policy_decisions_company_created",
        "policy_decisions",
        ["company_id", "created_at"],
    )
    op.create_index(
        "ix_policy_decisions_company_outcome",
        "policy_decisions",
        ["company_id", "outcome"],
    )
    op.create_index("ix_policy_decisions_correlation_id", "policy_decisions", ["correlation_id"])
    op.create_index("ix_policy_decisions_outcome", "policy_decisions", ["outcome"])
    op.create_index("ix_policy_decisions_resource_type", "policy_decisions", ["resource_type"])
    op.create_index("ix_policy_decisions_subject_user_id", "policy_decisions", ["subject_user_id"])


def downgrade() -> None:
    op.drop_index("ix_policy_decisions_subject_user_id", table_name="policy_decisions")
    op.drop_index("ix_policy_decisions_resource_type", table_name="policy_decisions")
    op.drop_index("ix_policy_decisions_outcome", table_name="policy_decisions")
    op.drop_index("ix_policy_decisions_correlation_id", table_name="policy_decisions")
    op.drop_index("ix_policy_decisions_company_outcome", table_name="policy_decisions")
    op.drop_index("ix_policy_decisions_company_created", table_name="policy_decisions")
    op.drop_index("ix_policy_decisions_company_id", table_name="policy_decisions")
    op.drop_index("ix_policy_decisions_action", table_name="policy_decisions")
    op.drop_table("policy_decisions")
