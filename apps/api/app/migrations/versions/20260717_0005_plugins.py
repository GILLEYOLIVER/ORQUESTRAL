"""Adiciona catálogo de plugins e credenciais criptografadas.

Revision ID: 20260717_0005
Revises: 20260716_0004
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260717_0005"
down_revision: str | None = "20260716_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    permissions = sa.table(
        "permissions",
        sa.column("code", sa.String()),
        sa.column("module_code", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        permissions,
        [
            {
                "code": "plugins.view",
                "module_code": "plugins",
                "action": "view",
                "description": "Visualizar plugins da empresa",
            },
            {
                "code": "plugins.manage",
                "module_code": "plugins",
                "action": "manage",
                "description": "Ativar plugins e administrar credenciais",
            },
        ],
    )
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT roles.id, permissions.id
        FROM roles CROSS JOIN permissions
        WHERE roles.name = 'Proprietário'
          AND permissions.code IN ('plugins.view', 'plugins.manage')
    """)

    op.create_table(
        "plugins",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", postgresql.CITEXT(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("authentication_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "manifest", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("created_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('installed', 'planned', 'disabled')", name="ck_plugins_status"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_plugins_code", "plugins", ["code"])
    op.create_index("ix_plugins_status", "plugins", ["status"])

    plugins = sa.table(
        "plugins",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("version", sa.String()),
        sa.column("description", sa.String()),
        sa.column("authentication_type", sa.String()),
        sa.column("status", sa.String()),
        sa.column("manifest", postgresql.JSONB()),
    )
    op.bulk_insert(
        plugins,
        [
            {
                "code": "generic_webhook",
                "name": "Webhook genérico",
                "version": "1.0.0",
                "description": "Recebe e envia eventos HTTP assinados.",
                "authentication_type": "secret",
                "status": "installed",
                "manifest": {"actions": ["send"], "triggers": ["receive"]},
            },
            {
                "code": "smtp_email",
                "name": "E-mail SMTP",
                "version": "1.0.0",
                "description": "Envio de mensagens por servidor SMTP.",
                "authentication_type": "username_password",
                "status": "installed",
                "manifest": {"actions": ["send_email"], "triggers": []},
            },
            {
                "code": "rest_api",
                "name": "API REST genérica",
                "version": "1.0.0",
                "description": "Integração segura com APIs HTTP externas.",
                "authentication_type": "api_key",
                "status": "installed",
                "manifest": {"actions": ["request"], "triggers": []},
            },
            {
                "code": "google_calendar",
                "name": "Google Calendar",
                "version": "0.0.0",
                "description": "Agenda e eventos do Google.",
                "authentication_type": "oauth2",
                "status": "planned",
                "manifest": {},
            },
            {
                "code": "whatsapp_business",
                "name": "WhatsApp Business",
                "version": "0.0.0",
                "description": "Mensagens por provedor oficial.",
                "authentication_type": "oauth2",
                "status": "planned",
                "manifest": {},
            },
        ],
        multiinsert=False,
    )

    op.create_table(
        "company_plugins",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("plugin_id", UUID, nullable=False),
        sa.Column("status", sa.String(20), server_default="inactive", nullable=False),
        sa.Column(
            "configuration",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("activated_at", TIMESTAMP, nullable=True),
        sa.Column("deactivated_at", TIMESTAMP, nullable=True),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_company_plugins_status"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "plugin_id", name="uq_company_plugins_company_plugin"),
    )
    op.create_index("ix_company_plugins_company_id", "company_plugins", ["company_id"])
    op.create_index("ix_company_plugins_plugin_id", "company_plugins", ["plugin_id"])

    op.create_table(
        "integration_credentials",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("plugin_id", UUID, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("encrypted_credentials", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("expires_at", TIMESTAMP, nullable=True),
        sa.Column("created_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'expired', 'revoked')", name="ck_integration_credentials_status"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_integration_credentials_company_id", "integration_credentials", ["company_id"]
    )
    op.create_index(
        "ix_integration_credentials_plugin_id", "integration_credentials", ["plugin_id"]
    )


def downgrade() -> None:
    op.drop_table("integration_credentials")
    op.drop_table("company_plugins")
    op.drop_table("plugins")
    op.execute("DELETE FROM permissions WHERE code IN ('plugins.view', 'plugins.manage')")
