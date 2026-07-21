"""Add metadata relationships, formulas and record types.

Revision ID: 20260721_0075
Revises: 20260721_0074
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0075"
down_revision: str | None = "20260721_0074"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _identity_columns() -> list[sa.Column[object]]:
    return [
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
    ]


def _common_constraints() -> list[sa.ForeignKeyConstraint]:
    return [
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["version_id"], ["metadata_entity_versions.id"], ondelete="CASCADE"
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "metadata_relationship_definitions",
        *_identity_columns(),
        sa.Column("source_field_key", sa.String(80), nullable=False),
        sa.Column("target_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_type", sa.String(24), nullable=False),
        sa.Column("on_delete", sa.String(16), server_default="restrict", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        *_common_constraints(),
        sa.ForeignKeyConstraint(
            ["target_definition_id"],
            ["metadata_entity_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "relationship_type IN ('many_to_one', 'one_to_one')",
            name="ck_metadata_relationship_type",
        ),
        sa.CheckConstraint("on_delete = 'restrict'", name="ck_metadata_relationship_on_delete"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "version_id", "key", name="uq_metadata_relationship_key"),
    )
    op.create_index(
        "ix_metadata_relationship_company_version",
        "metadata_relationship_definitions",
        ["company_id", "version_id"],
    )
    op.create_index(
        "ix_metadata_relationship_target",
        "metadata_relationship_definitions",
        ["company_id", "target_definition_id"],
    )
    for column in ("company_id", "version_id", "target_definition_id"):
        op.create_index(
            f"ix_metadata_relationship_definitions_{column}",
            "metadata_relationship_definitions",
            [column],
        )

    op.create_table(
        "metadata_formula_definitions",
        *_identity_columns(),
        sa.Column("target_field_key", sa.String(80), nullable=False),
        sa.Column("expression", postgresql.JSONB(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        *_common_constraints(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "version_id", "key", name="uq_metadata_formula_key"),
        sa.UniqueConstraint(
            "company_id",
            "version_id",
            "target_field_key",
            name="uq_metadata_formula_target",
        ),
    )
    op.create_index(
        "ix_metadata_formula_company_version",
        "metadata_formula_definitions",
        ["company_id", "version_id"],
    )
    for column in ("company_id", "version_id"):
        op.create_index(
            f"ix_metadata_formula_definitions_{column}",
            "metadata_formula_definitions",
            [column],
        )

    op.create_table(
        "metadata_record_type_definitions",
        *_identity_columns(),
        sa.Column("description", sa.Text()),
        sa.Column("layout_key", sa.String(80), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        *_common_constraints(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "version_id", "key", name="uq_metadata_record_type_key"),
    )
    op.create_index(
        "ix_metadata_record_type_company_version",
        "metadata_record_type_definitions",
        ["company_id", "version_id"],
    )
    for column in ("company_id", "version_id"):
        op.create_index(
            f"ix_metadata_record_type_definitions_{column}",
            "metadata_record_type_definitions",
            [column],
        )

    op.add_column("metadata_records", sa.Column("record_type_key", sa.String(80)))
    op.add_column("metadata_record_revisions", sa.Column("record_type_key", sa.String(80)))
    op.create_index(
        "ix_metadata_record_company_type",
        "metadata_records",
        ["company_id", "definition_id", "record_type_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_metadata_record_company_type", table_name="metadata_records")
    op.drop_column("metadata_record_revisions", "record_type_key")
    op.drop_column("metadata_records", "record_type_key")
    op.drop_table("metadata_record_type_definitions")
    op.drop_table("metadata_formula_definitions")
    op.drop_table("metadata_relationship_definitions")
