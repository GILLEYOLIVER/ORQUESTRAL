"""Create secure custom metadata records.

Revision ID: 20260721_0031
Revises: 20260721_0030
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0031"
down_revision: str | None = "20260721_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = (
    ("metadata.records.view", "metadata", "records.view", "Visualizar registros personalizados"),
    ("metadata.records.create", "metadata", "records.create", "Criar registros personalizados"),
    ("metadata.records.update", "metadata", "records.update", "Alterar registros personalizados"),
    ("metadata.records.delete", "metadata", "records.delete", "Excluir registros personalizados"),
)


def upgrade() -> None:
    op.create_table(
        "metadata_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("record_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("record_version > 0", name="ck_metadata_record_version_positive"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["definition_id"], ["metadata_entity_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["schema_version_id"], ["metadata_entity_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "definition_id", "idempotency_key", name="uq_metadata_record_idempotency"
        ),
    )
    op.create_index("ix_metadata_records_company_id", "metadata_records", ["company_id"])
    op.create_index("ix_metadata_records_definition_id", "metadata_records", ["definition_id"])
    op.create_index(
        "ix_metadata_records_schema_version_id", "metadata_records", ["schema_version_id"]
    )
    op.create_index("ix_metadata_records_deleted_at", "metadata_records", ["deleted_at"])
    op.create_index(
        "ix_metadata_record_company_definition_active",
        "metadata_records",
        ["company_id", "definition_id", "deleted_at"],
    )
    op.create_table(
        "metadata_record_revisions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("change_type", sa.String(length=16), nullable=False),
        sa.Column("values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("changed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("revision > 0", name="ck_metadata_record_revision_positive"),
        sa.CheckConstraint(
            "change_type IN ('created', 'updated')", name="ck_metadata_record_revision_change_type"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["definition_id"], ["metadata_entity_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["record_id"], ["metadata_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["schema_version_id"], ["metadata_entity_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_id", "revision", name="uq_metadata_record_revision"),
    )
    op.create_index(
        "ix_metadata_record_revisions_company_id", "metadata_record_revisions", ["company_id"]
    )
    op.create_index(
        "ix_metadata_record_revisions_definition_id", "metadata_record_revisions", ["definition_id"]
    )
    op.create_index(
        "ix_metadata_record_revisions_record_id", "metadata_record_revisions", ["record_id"]
    )
    op.create_index(
        "ix_metadata_record_revision_company_record",
        "metadata_record_revisions",
        ["company_id", "record_id"],
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
          AND permissions.code IN (
              'metadata.records.view', 'metadata.records.create',
              'metadata.records.update', 'metadata.records.delete'
          )
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE code IN (
                'metadata.records.view', 'metadata.records.create',
                'metadata.records.update', 'metadata.records.delete'
            )
        )
        """
    )
    op.execute(
        """
        DELETE FROM permissions WHERE code IN (
            'metadata.records.view', 'metadata.records.create',
            'metadata.records.update', 'metadata.records.delete'
        )
        """
    )
    op.drop_index(
        "ix_metadata_record_revision_company_record", table_name="metadata_record_revisions"
    )
    op.drop_index("ix_metadata_record_revisions_record_id", table_name="metadata_record_revisions")
    op.drop_index(
        "ix_metadata_record_revisions_definition_id", table_name="metadata_record_revisions"
    )
    op.drop_index("ix_metadata_record_revisions_company_id", table_name="metadata_record_revisions")
    op.drop_table("metadata_record_revisions")
    op.drop_index("ix_metadata_record_company_definition_active", table_name="metadata_records")
    op.drop_index("ix_metadata_records_deleted_at", table_name="metadata_records")
    op.drop_index("ix_metadata_records_schema_version_id", table_name="metadata_records")
    op.drop_index("ix_metadata_records_definition_id", table_name="metadata_records")
    op.drop_index("ix_metadata_records_company_id", table_name="metadata_records")
    op.drop_table("metadata_records")
