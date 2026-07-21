"""Add versioned metadata layouts, views and validation rules.

Revision ID: 20260721_0072
Revises: 20260721_0071
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0072"
down_revision: str | None = "20260721_0071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metadata_layout_definitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column(
            "sections", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["version_id"], ["metadata_entity_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "version_id", "key", name="uq_metadata_layout_key"),
    )
    op.create_index(
        "ix_metadata_layout_company_version",
        "metadata_layout_definitions",
        ["company_id", "version_id"],
    )
    op.create_index(
        "ix_metadata_layout_definitions_company_id", "metadata_layout_definitions", ["company_id"]
    )
    op.create_index(
        "ix_metadata_layout_definitions_version_id", "metadata_layout_definitions", ["version_id"]
    )

    op.create_table(
        "metadata_view_definitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column(
            "columns", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "filters", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "sorting", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["version_id"], ["metadata_entity_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "version_id", "key", name="uq_metadata_view_key"),
    )
    op.create_index(
        "ix_metadata_view_company_version",
        "metadata_view_definitions",
        ["company_id", "version_id"],
    )
    op.create_index(
        "ix_metadata_view_definitions_company_id", "metadata_view_definitions", ["company_id"]
    )
    op.create_index(
        "ix_metadata_view_definitions_version_id", "metadata_view_definitions", ["version_id"]
    )

    op.create_table(
        "metadata_validation_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("field_key", sa.String(80), nullable=False),
        sa.Column("operator", sa.String(24), nullable=False),
        sa.Column("comparison_value", postgresql.JSONB()),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "operator IN ('equals', 'not_equals', 'greater_than', 'less_than', 'contains', 'is_empty', 'is_not_empty')",
            name="ck_metadata_validation_rule_operator",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["version_id"], ["metadata_entity_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "version_id", "key", name="uq_metadata_validation_rule_key"
        ),
    )
    op.create_index(
        "ix_metadata_validation_rule_company_version",
        "metadata_validation_rules",
        ["company_id", "version_id"],
    )
    op.create_index(
        "ix_metadata_validation_rules_company_id", "metadata_validation_rules", ["company_id"]
    )
    op.create_index(
        "ix_metadata_validation_rules_version_id", "metadata_validation_rules", ["version_id"]
    )


def downgrade() -> None:
    op.drop_table("metadata_validation_rules")
    op.drop_table("metadata_view_definitions")
    op.drop_table("metadata_layout_definitions")
