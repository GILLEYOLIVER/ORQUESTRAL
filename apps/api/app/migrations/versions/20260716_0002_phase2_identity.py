"""Adiciona empresas, usuários, vínculos e autenticação.

Revision ID: 20260716_0002
Revises: 20260716_0001
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0002"
down_revision: str | None = "20260716_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMP = sa.DateTime(timezone=True)


def _id() -> sa.Column[object]:
    return sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False)


def _created_at() -> sa.Column[object]:
    return sa.Column("created_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False)


def _updated_at() -> sa.Column[object]:
    return sa.Column("updated_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "companies",
        _id(),
        sa.Column("legal_name", sa.String(200), nullable=False),
        sa.Column("trade_name", sa.String(200), nullable=False),
        sa.Column("document_number", sa.String(32), nullable=False),
        sa.Column("slug", postgresql.CITEXT(), nullable=False),
        sa.Column("status", sa.String(20), server_default="trial", nullable=False),
        sa.Column("timezone", sa.String(64), server_default="America/Sao_Paulo", nullable=False),
        sa.Column("language", sa.String(16), server_default="pt-BR", nullable=False),
        _created_at(),
        _updated_at(),
        sa.Column("deleted_at", TIMESTAMP, nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'trial', 'cancelled')",
            name="ck_companies_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_number"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_companies_document_number", "companies", ["document_number"])
    op.create_index("ix_companies_slug", "companies", ["slug"])

    op.create_table(
        "users",
        _id(),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), server_default="invited", nullable=False),
        sa.Column("is_platform_admin", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("last_login_at", TIMESTAMP, nullable=True),
        _created_at(),
        _updated_at(),
        sa.Column("deleted_at", TIMESTAMP, nullable=True),
        sa.CheckConstraint("status IN ('active', 'invited', 'disabled')", name="ck_users_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "company_users",
        _id(),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("role_id", UUID, nullable=True),
        sa.Column("status", sa.String(20), server_default="invited", nullable=False),
        sa.Column("is_owner", sa.Boolean(), server_default=sa.false(), nullable=False),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "status IN ('active', 'invited', 'disabled')", name="ck_company_users_status"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "user_id", name="uq_company_users_company_user"),
    )
    op.create_index("ix_company_users_company_id", "company_users", ["company_id"])
    op.create_index("ix_company_users_user_id", "company_users", ["user_id"])

    op.create_table(
        "auth_sessions",
        _id(),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("selected_company_id", UUID, nullable=True),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=False),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("expires_at", TIMESTAMP, nullable=False),
        sa.Column("last_used_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", TIMESTAMP, nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["selected_company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_token_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index(
        "ix_auth_sessions_selected_company_id", "auth_sessions", ["selected_company_id"]
    )
    op.create_index("ix_auth_sessions_refresh_token_hash", "auth_sessions", ["refresh_token_hash"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_index("ix_auth_sessions_revoked_at", "auth_sessions", ["revoked_at"])

    op.create_table(
        "auth_attempts",
        _id(),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_attempts_email", "auth_attempts", ["email"])
    op.create_index("ix_auth_attempts_ip_address", "auth_attempts", ["ip_address"])
    op.create_index("ix_auth_attempts_succeeded", "auth_attempts", ["succeeded"])
    op.create_index("ix_auth_attempts_created_at", "auth_attempts", ["created_at"])

    op.create_table(
        "password_reset_tokens",
        _id(),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("requested_ip", sa.String(64), nullable=False),
        sa.Column("expires_at", TIMESTAMP, nullable=False),
        sa.Column("used_at", TIMESTAMP, nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"])
    op.create_index("ix_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"])

    op.create_table(
        "company_invitations",
        _id(),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("invited_by_user_id", UUID, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", TIMESTAMP, nullable=False),
        sa.Column("accepted_at", TIMESTAMP, nullable=True),
        sa.Column("revoked_at", TIMESTAMP, nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_company_invitations_company_id", "company_invitations", ["company_id"])
    op.create_index("ix_company_invitations_user_id", "company_invitations", ["user_id"])
    op.create_index(
        "ix_company_invitations_invited_by_user_id",
        "company_invitations",
        ["invited_by_user_id"],
    )
    op.create_index("ix_company_invitations_token_hash", "company_invitations", ["token_hash"])
    op.create_index("ix_company_invitations_expires_at", "company_invitations", ["expires_at"])


def downgrade() -> None:
    op.drop_table("company_invitations")
    op.drop_table("password_reset_tokens")
    op.drop_table("auth_attempts")
    op.drop_table("auth_sessions")
    op.drop_table("company_users")
    op.drop_table("users")
    op.drop_table("companies")
