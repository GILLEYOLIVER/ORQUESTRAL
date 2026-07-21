"""Create versioned metadata platform foundation.

Revision ID: 20260721_0030
Revises: 20260721_0029
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0030"
down_revision: str | None = "20260721_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = (
    ("metadata.view", "metadata", "view", "Visualizar definicoes de metadados"),
    ("metadata.configure", "metadata", "configure", "Configurar definicoes de metadados"),
    ("metadata.publish", "metadata", "publish", "Publicar definicoes de metadados"),
)


def upgrade() -> None:
    op.create_table(
        "metadata_entity_definitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("plural_label", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("published_version", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')", name="ck_metadata_entity_status"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "key", name="uq_metadata_entity_company_key"),
    )
    op.create_index(
        "ix_metadata_entity_definitions_company_id", "metadata_entity_definitions", ["company_id"]
    )
    op.create_index(
        "ix_metadata_entity_company_status", "metadata_entity_definitions", ["company_id", "status"]
    )

    op.create_table(
        "metadata_entity_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("schema_checksum", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("published_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'validated', 'published', 'retired')",
            name="ck_metadata_entity_version_status",
        ),
        sa.CheckConstraint("version > 0", name="ck_metadata_entity_version_positive"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["definition_id"], ["metadata_entity_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("definition_id", "version", name="uq_metadata_entity_version_number"),
    )
    op.create_index(
        "ix_metadata_entity_versions_company_id", "metadata_entity_versions", ["company_id"]
    )
    op.create_index(
        "ix_metadata_entity_versions_definition_id", "metadata_entity_versions", ["definition_id"]
    )
    op.create_index(
        "ix_metadata_entity_version_company_status",
        "metadata_entity_versions",
        ["company_id", "status"],
    )

    op.create_table(
        "metadata_field_definitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("data_type", sa.String(length=24), nullable=False),
        sa.Column("required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("unique_values", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("searchable", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("default_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "data_type IN ('text', 'long_text', 'integer', 'decimal', 'boolean', 'date', 'datetime', 'email', 'phone', 'url', 'uuid', 'json')",
            name="ck_metadata_field_data_type",
        ),
        sa.CheckConstraint("position >= 0", name="ck_metadata_field_position_nonnegative"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["version_id"], ["metadata_entity_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "key", name="uq_metadata_field_version_key"),
    )
    op.create_index(
        "ix_metadata_field_definitions_company_id", "metadata_field_definitions", ["company_id"]
    )
    op.create_index(
        "ix_metadata_field_definitions_version_id", "metadata_field_definitions", ["version_id"]
    )
    op.create_index(
        "ix_metadata_field_company_version",
        "metadata_field_definitions",
        ["company_id", "version_id"],
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO permissions (code, module_code, action, description)
            VALUES (:code, :module_code, :action, :description)
            ON CONFLICT (code) DO UPDATE SET
                module_code = EXCLUDED.module_code,
                action = EXCLUDED.action,
                description = EXCLUDED.description
            """
        ),
        [
            {"code": code, "module_code": module, "action": action, "description": description}
            for code, module, action, description in PERMISSIONS
        ],
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT roles.id, permissions.id
        FROM roles CROSS JOIN permissions
        WHERE roles.is_system_role = true
          AND lower(roles.name) = lower('Proprietário')
          AND permissions.module_code = 'metadata'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (SELECT id FROM permissions WHERE module_code = 'metadata')
        """
    )
    op.execute("DELETE FROM permissions WHERE module_code = 'metadata'")
    op.drop_index("ix_metadata_field_company_version", table_name="metadata_field_definitions")
    op.drop_index(
        "ix_metadata_field_definitions_version_id", table_name="metadata_field_definitions"
    )
    op.drop_index(
        "ix_metadata_field_definitions_company_id", table_name="metadata_field_definitions"
    )
    op.drop_table("metadata_field_definitions")
    op.drop_index(
        "ix_metadata_entity_version_company_status", table_name="metadata_entity_versions"
    )
    op.drop_index(
        "ix_metadata_entity_versions_definition_id", table_name="metadata_entity_versions"
    )
    op.drop_index("ix_metadata_entity_versions_company_id", table_name="metadata_entity_versions")
    op.drop_table("metadata_entity_versions")
    op.drop_index("ix_metadata_entity_company_status", table_name="metadata_entity_definitions")
    op.drop_index(
        "ix_metadata_entity_definitions_company_id", table_name="metadata_entity_definitions"
    )
    op.drop_table("metadata_entity_definitions")
