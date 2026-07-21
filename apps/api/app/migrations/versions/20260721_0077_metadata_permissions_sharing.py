"""Add metadata entity, field and record sharing security.

Revision ID: 20260721_0077
Revises: 20260721_0076
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0077"
down_revision: str | None = "20260721_0076"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("metadata_records", sa.Column("owner_user_id", _uuid()))
    op.create_foreign_key(
        "fk_metadata_records_owner_user_id_users",
        "metadata_records",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_metadata_records_owner_user_id", "metadata_records", ["owner_user_id"]
    )
    op.execute(
        "UPDATE metadata_records SET owner_user_id = created_by_user_id "
        "WHERE owner_user_id IS NULL"
    )

    op.create_table(
        "metadata_entity_access_rules",
        sa.Column("id", _uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", _uuid(), nullable=False),
        sa.Column("definition_id", _uuid(), nullable=False),
        sa.Column("subject_type", sa.String(16), nullable=False),
        sa.Column("subject_id", _uuid(), nullable=False),
        sa.Column("can_view", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("can_create", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("can_update", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("can_delete", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("can_export", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("record_scope", sa.String(24), server_default="owned", nullable=False),
        sa.Column("created_by_user_id", _uuid()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "subject_type IN ('user', 'role')", name="ck_metadata_entity_access_subject_type"
        ),
        sa.CheckConstraint(
            "record_scope IN ('all', 'owned', 'owned_shared')",
            name="ck_metadata_entity_access_record_scope",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["definition_id"], ["metadata_entity_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "definition_id",
            "subject_type",
            "subject_id",
            name="uq_metadata_entity_access_subject",
        ),
    )
    for column in ("company_id", "definition_id", "subject_id"):
        op.create_index(
            f"ix_metadata_entity_access_rules_{column}",
            "metadata_entity_access_rules",
            [column],
        )
    op.create_index(
        "ix_metadata_entity_access_company_definition",
        "metadata_entity_access_rules",
        ["company_id", "definition_id"],
    )

    op.create_table(
        "metadata_field_access_rules",
        sa.Column("id", _uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", _uuid(), nullable=False),
        sa.Column("definition_id", _uuid(), nullable=False),
        sa.Column("field_key", sa.String(80), nullable=False),
        sa.Column("subject_type", sa.String(16), nullable=False),
        sa.Column("subject_id", _uuid(), nullable=False),
        sa.Column("can_view", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("can_edit", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_by_user_id", _uuid()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "subject_type IN ('user', 'role')", name="ck_metadata_field_access_subject_type"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["definition_id"], ["metadata_entity_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "definition_id",
            "field_key",
            "subject_type",
            "subject_id",
            name="uq_metadata_field_access_subject",
        ),
    )
    for column in ("company_id", "definition_id", "subject_id"):
        op.create_index(
            f"ix_metadata_field_access_rules_{column}",
            "metadata_field_access_rules",
            [column],
        )
    op.create_index(
        "ix_metadata_field_access_company_definition",
        "metadata_field_access_rules",
        ["company_id", "definition_id"],
    )

    op.create_table(
        "metadata_record_shares",
        sa.Column("id", _uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", _uuid(), nullable=False),
        sa.Column("definition_id", _uuid(), nullable=False),
        sa.Column("record_id", _uuid(), nullable=False),
        sa.Column("subject_type", sa.String(16), nullable=False),
        sa.Column("subject_id", _uuid(), nullable=False),
        sa.Column("can_view", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("can_edit", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_by_user_id", _uuid()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "subject_type IN ('user', 'role')", name="ck_metadata_record_share_subject_type"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["definition_id"], ["metadata_entity_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["record_id"], ["metadata_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "record_id",
            "subject_type",
            "subject_id",
            name="uq_metadata_record_share_subject",
        ),
    )
    for column in ("company_id", "definition_id", "record_id", "subject_id"):
        op.create_index(
            f"ix_metadata_record_shares_{column}", "metadata_record_shares", [column]
        )
    op.create_index(
        "ix_metadata_record_share_company_definition",
        "metadata_record_shares",
        ["company_id", "definition_id"],
    )


def downgrade() -> None:
    op.drop_table("metadata_record_shares")
    op.drop_table("metadata_field_access_rules")
    op.drop_table("metadata_entity_access_rules")
    op.drop_index("ix_metadata_records_owner_user_id", table_name="metadata_records")
    op.drop_constraint(
        "fk_metadata_records_owner_user_id_users", "metadata_records", type_="foreignkey"
    )
    op.drop_column("metadata_records", "owner_user_id")
