"""marketplace package supply chain

Revision ID: 20260729_0121
Revises: 20260729_0120
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260729_0121"
down_revision: str | None = "20260729_0120"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plugin_publishers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", postgresql.CITEXT(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("public_key", sa.String(128), nullable=False),
        sa.Column("key_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), server_default="trusted", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('trusted', 'revoked')", name="ck_plugin_publishers_status"
        ),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("key_fingerprint"),
    )
    op.create_index("ix_plugin_publishers_code", "plugin_publishers", ["code"])
    op.create_table(
        "plugin_package_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plugin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("publisher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("artifact_digest", sa.String(64), nullable=False),
        sa.Column("signature", sa.String(128), nullable=False),
        sa.Column("min_platform_version", sa.String(32), nullable=False),
        sa.Column("max_platform_version", sa.String(32)),
        sa.Column(
            "requested_permissions",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), server_default="published", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('published', 'revoked')", name="ck_plugin_package_versions_status"
        ),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["publisher_id"], ["plugin_publishers.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "plugin_id", "version", name="uq_plugin_package_versions_release"
        ),
    )
    op.create_index(
        "ix_plugin_package_versions_plugin_id", "plugin_package_versions", ["plugin_id"]
    )
    op.create_index(
        "ix_plugin_package_versions_publisher_id",
        "plugin_package_versions",
        ["publisher_id"],
    )
    op.add_column(
        "company_plugins",
        sa.Column("installed_version_id", postgresql.UUID(as_uuid=True)),
    )
    op.create_foreign_key(
        "fk_company_plugins_installed_version",
        "company_plugins",
        "plugin_package_versions",
        ["installed_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_company_plugins_installed_version_id",
        "company_plugins",
        ["installed_version_id"],
    )
    op.create_table(
        "company_plugin_installations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plugin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("plugins.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "package_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("plugin_package_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "previous_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("plugin_package_versions.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.String(20), server_default="installed", nullable=False),
        sa.Column("operation", sa.String(20), server_default="install", nullable=False),
        sa.Column(
            "installed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("installed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('installed', 'replaced')",
            name="ck_company_plugin_installations_status",
        ),
        sa.CheckConstraint(
            "operation IN ('install', 'rollback')",
            name="ck_company_plugin_installations_operation",
        ),
    )
    for column in (
        "company_id",
        "plugin_id",
        "package_version_id",
        "previous_version_id",
        "installed_by_user_id",
        "installed_at",
    ):
        op.create_index(
            f"ix_company_plugin_installations_{column}",
            "company_plugin_installations",
            [column],
        )
    op.execute("ALTER TABLE company_plugin_installations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE company_plugin_installations FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("company_plugin_installations")
    op.drop_index("ix_company_plugins_installed_version_id", table_name="company_plugins")
    op.drop_constraint(
        "fk_company_plugins_installed_version", "company_plugins", type_="foreignkey"
    )
    op.drop_column("company_plugins", "installed_version_id")
    op.drop_table("plugin_package_versions")
    op.drop_table("plugin_publishers")
