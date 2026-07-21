"""Add secure read-only access links.

Revision ID: 20260721_0074
Revises: 20260721_0073
Create Date: 2026-07-21 16:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0074"
down_revision: str | None = "20260721_0073"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "read_only_access_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("usage_count >= 0", name="ck_read_only_access_links_usage_count"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    for column in (
        "company_id",
        "target_user_id",
        "created_by_user_id",
        "token_hash",
        "expires_at",
        "revoked_at",
        "created_at",
    ):
        op.create_index(
            f"ix_read_only_access_links_{column}",
            "read_only_access_links",
            [column],
        )
    op.add_column(
        "auth_sessions",
        sa.Column("access_mode", sa.String(length=24), server_default="standard", nullable=False),
    )
    op.add_column(
        "auth_sessions",
        sa.Column("read_only_access_link_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_auth_sessions_access_mode",
        "auth_sessions",
        "access_mode IN ('standard', 'read_only')",
    )
    op.create_index("ix_auth_sessions_access_mode", "auth_sessions", ["access_mode"])
    op.create_index(
        "ix_auth_sessions_read_only_access_link_id",
        "auth_sessions",
        ["read_only_access_link_id"],
    )
    op.create_foreign_key(
        "fk_auth_sessions_read_only_access_link_id",
        "auth_sessions",
        "read_only_access_links",
        ["read_only_access_link_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        """
        INSERT INTO permissions (id, code, module_code, action, description)
        VALUES (
            gen_random_uuid(),
            'access_links.manage',
            'users',
            'access_links.manage',
            'Gerar links seguros de acesso somente leitura'
        )
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT roles.id, permissions.id
          FROM roles
          JOIN permissions ON permissions.code = 'access_links.manage'
         WHERE roles.is_system_role = true
           AND lower(roles.name) = lower('Proprietário')
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_auth_sessions_read_only_access_link_id",
        "auth_sessions",
        type_="foreignkey",
    )
    op.drop_index("ix_auth_sessions_read_only_access_link_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_access_mode", table_name="auth_sessions")
    op.drop_constraint("ck_auth_sessions_access_mode", "auth_sessions", type_="check")
    op.drop_column("auth_sessions", "read_only_access_link_id")
    op.drop_column("auth_sessions", "access_mode")
    op.drop_table("read_only_access_links")
    op.execute("DELETE FROM permissions WHERE code = 'access_links.manage'")
