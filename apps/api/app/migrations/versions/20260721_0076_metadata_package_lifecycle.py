"""Add metadata package release and installation lifecycle.

Revision ID: 20260721_0076
Revises: 20260721_0075
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0076"
down_revision: str | None = "20260721_0075"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metadata_package_catalogs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "key", name="uq_metadata_package_catalog_key"),
    )
    op.create_index(
        "ix_metadata_package_catalog_company", "metadata_package_catalogs", ["company_id", "key"]
    )
    op.create_index(
        "ix_metadata_package_catalogs_company_id", "metadata_package_catalogs", ["company_id"]
    )

    op.create_table(
        "metadata_package_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("package_catalog_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), server_default="draft", nullable=False),
        sa.Column("source_environment", sa.String(16), nullable=False),
        sa.Column(
            "dependencies",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("artifact", postgresql.JSONB(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("published_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'validated', 'published', 'retired')",
            name="ck_metadata_package_version_status",
        ),
        sa.CheckConstraint(
            "source_environment IN ('local', 'testing', 'development', 'staging', 'production')",
            name="ck_metadata_package_source_environment",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["package_catalog_id"], ["metadata_package_catalogs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["entity_definition_id"], ["metadata_entity_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "package_catalog_id", "version", name="uq_metadata_package_version_number"
        ),
    )
    for column in ("company_id", "package_catalog_id", "entity_definition_id"):
        op.create_index(
            f"ix_metadata_package_versions_{column}", "metadata_package_versions", [column]
        )
    op.create_index(
        "ix_metadata_package_version_company_status",
        "metadata_package_versions",
        ["company_id", "status"],
    )

    op.create_table(
        "metadata_package_installations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("package_key", sa.String(80), nullable=False),
        sa.Column("package_version", sa.String(32), nullable=False),
        sa.Column("source_checksum", sa.String(64), nullable=False),
        sa.Column("target_environment", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), server_default="installed", nullable=False),
        sa.Column("installed_definition_id", postgresql.UUID(as_uuid=True)),
        sa.Column("installed_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "installed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('installed', 'removed')", name="ck_metadata_package_installation_status"
        ),
        sa.CheckConstraint(
            "target_environment IN ('local', 'testing', 'development', 'staging', 'production')",
            name="ck_metadata_package_target_environment",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["installed_definition_id"], ["metadata_entity_definitions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["installed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "package_key",
            "package_version",
            "target_environment",
            name="uq_metadata_package_installation_release",
        ),
    )
    for column in ("company_id", "installed_definition_id"):
        op.create_index(
            f"ix_metadata_package_installations_{column}",
            "metadata_package_installations",
            [column],
        )
    op.create_index(
        "ix_metadata_package_installation_company_status",
        "metadata_package_installations",
        ["company_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("metadata_package_installations")
    op.drop_table("metadata_package_versions")
    op.drop_table("metadata_package_catalogs")
