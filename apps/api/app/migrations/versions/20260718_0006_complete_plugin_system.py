"""Completa runtime, catálogo e auditoria de plugins da Fase 5.

Revision ID: 20260718_0006
Revises: 20260717_0005
Create Date: 2026-07-18
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260718_0006"
down_revision: str | None = "20260717_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMP = sa.DateTime(timezone=True)

PLUGINS = (
    {
        "code": "generic_webhook",
        "name": "Webhook genérico",
        "version": "1.0.0",
        "description": "Recebe e envia eventos HTTP assinados.",
        "authentication_type": "secret",
        "manifest": {
            "credential_fields": [
                {"key": "url", "label": "URL de destino", "kind": "url", "required": True, "secret": False, "placeholder": "https://exemplo.com/webhook", "default": None},
                {"key": "signing_secret", "label": "Segredo de assinatura", "kind": "password", "required": False, "secret": True, "placeholder": None, "default": None},
            ],
            "configuration_fields": [], "tools": [{"code": "send", "name": "Enviar webhook", "description": "Envia um evento HTTP assinado."}],
            "triggers": ["receive"], "actions": ["send"], "supports_token_refresh": False, "supports_webhooks": True,
        },
    },
    {
        "code": "smtp_email", "name": "E-mail SMTP", "version": "1.0.0", "description": "Envio de mensagens por servidor SMTP.", "authentication_type": "username_password",
        "manifest": {"credential_fields": [
            {"key": "host", "label": "Servidor SMTP", "kind": "text", "required": True, "secret": False, "placeholder": None, "default": None},
            {"key": "port", "label": "Porta", "kind": "integer", "required": True, "secret": False, "placeholder": None, "default": 587},
            {"key": "username", "label": "Usuário", "kind": "text", "required": False, "secret": False, "placeholder": None, "default": None},
            {"key": "password", "label": "Senha", "kind": "password", "required": False, "secret": True, "placeholder": None, "default": None},
            {"key": "use_tls", "label": "Usar STARTTLS", "kind": "boolean", "required": False, "secret": False, "placeholder": None, "default": True}],
            "configuration_fields": [], "tools": [{"code": "send_email", "name": "Enviar e-mail", "description": "Envia uma mensagem pelo SMTP configurado."}], "triggers": [], "actions": ["send_email"], "supports_token_refresh": False, "supports_webhooks": False},
    },
    {
        "code": "imap_email", "name": "E-mail IMAP", "version": "1.0.0", "description": "Leitura de caixas de e-mail via IMAP ou provedor compatível.", "authentication_type": "username_password",
        "manifest": {"credential_fields": [
            {"key": "host", "label": "Servidor IMAP", "kind": "text", "required": True, "secret": False, "placeholder": None, "default": None},
            {"key": "port", "label": "Porta", "kind": "integer", "required": True, "secret": False, "placeholder": None, "default": 993},
            {"key": "username", "label": "Usuário", "kind": "text", "required": True, "secret": False, "placeholder": None, "default": None},
            {"key": "password", "label": "Senha ou token", "kind": "password", "required": True, "secret": True, "placeholder": None, "default": None},
            {"key": "use_ssl", "label": "Usar SSL", "kind": "boolean", "required": False, "secret": False, "placeholder": None, "default": True}],
            "configuration_fields": [], "tools": [], "triggers": ["email_received"], "actions": [], "supports_token_refresh": False, "supports_webhooks": False},
    },
    {
        "code": "google_calendar", "name": "Google Calendar", "version": "1.0.0", "description": "Agenda e eventos do Google por OAuth 2.0.", "authentication_type": "oauth2",
        "manifest": {"credential_fields": [
            {"key": "access_token", "label": "Token de acesso OAuth", "kind": "password", "required": True, "secret": True, "placeholder": None, "default": None},
            {"key": "refresh_token", "label": "Token de renovação", "kind": "password", "required": False, "secret": True, "placeholder": None, "default": None}],
            "configuration_fields": [], "tools": [{"code": "calendar_event", "name": "Gerenciar evento", "description": "Cria e atualiza eventos."}], "triggers": ["event_changed"], "actions": ["list_events", "create_event", "update_event"], "supports_token_refresh": True, "supports_webhooks": True},
    },
    {
        "code": "whatsapp_business", "name": "WhatsApp Business", "version": "1.0.0", "description": "Mensagens pela API oficial do WhatsApp Business.", "authentication_type": "oauth2",
        "manifest": {"credential_fields": [
            {"key": "access_token", "label": "Token de acesso", "kind": "password", "required": True, "secret": True, "placeholder": None, "default": None},
            {"key": "phone_number_id", "label": "ID do número de telefone", "kind": "text", "required": True, "secret": False, "placeholder": None, "default": None},
            {"key": "api_version", "label": "Versão da Graph API", "kind": "text", "required": True, "secret": False, "placeholder": "vXX.X", "default": None}],
            "configuration_fields": [], "tools": [{"code": "send_message", "name": "Enviar mensagem", "description": "Envia mensagem pelo provedor oficial."}], "triggers": ["message_received", "message_status"], "actions": ["send_message"], "supports_token_refresh": True, "supports_webhooks": True},
    },
    {
        "code": "external_postgresql", "name": "PostgreSQL externo", "version": "1.0.0", "description": "Acesso controlado a um banco PostgreSQL externo.", "authentication_type": "connection_string",
        "manifest": {"credential_fields": [{"key": "dsn", "label": "String de conexão", "kind": "password", "required": True, "secret": True, "placeholder": "postgresql://...", "default": None}],
            "configuration_fields": [], "tools": [{"code": "query", "name": "Consulta PostgreSQL", "description": "Executa consultas permitidas no banco externo."}], "triggers": [], "actions": ["query"], "supports_token_refresh": False, "supports_webhooks": False},
    },
    {
        "code": "rest_api", "name": "API REST genérica", "version": "1.0.0", "description": "Integração segura com APIs HTTP externas.", "authentication_type": "api_key",
        "manifest": {"credential_fields": [
            {"key": "base_url", "label": "URL base", "kind": "url", "required": True, "secret": False, "placeholder": "https://api.exemplo.com", "default": None},
            {"key": "api_key", "label": "Chave da API", "kind": "password", "required": False, "secret": True, "placeholder": None, "default": None},
            {"key": "auth_header", "label": "Cabeçalho de autenticação", "kind": "text", "required": False, "secret": False, "placeholder": None, "default": "Authorization"}],
            "configuration_fields": [], "tools": [{"code": "request", "name": "Requisição HTTP", "description": "Executa uma chamada autenticada."}], "triggers": [], "actions": ["request"], "supports_token_refresh": False, "supports_webhooks": False},
    },
)


def upgrade() -> None:
    op.add_column("company_plugins", sa.Column("created_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False))
    op.add_column("company_plugins", sa.Column("updated_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False))
    op.add_column("integration_credentials", sa.Column("credential_fields", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))

    op.create_table(
        "plugin_connection_tests",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("plugin_id", UUID, nullable=False),
        sa.Column("credential_id", UUID, nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("duration_ms >= 0", name="ck_plugin_connection_tests_duration"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["credential_id"], ["integration_credentials.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plugin_connection_tests_company_id", "plugin_connection_tests", ["company_id"])
    op.create_index("ix_plugin_connection_tests_plugin_id", "plugin_connection_tests", ["plugin_id"])
    op.create_index("ix_plugin_connection_tests_credential_id", "plugin_connection_tests", ["credential_id"])
    op.create_index("ix_plugin_connection_tests_created_at", "plugin_connection_tests", ["created_at"])

    connection = op.get_bind()
    statement = sa.text("""
        INSERT INTO plugins (code, name, version, description, authentication_type, status, manifest)
        VALUES (:code, :name, :version, :description, :authentication_type, 'installed', CAST(:manifest AS jsonb))
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            version = EXCLUDED.version,
            description = EXCLUDED.description,
            authentication_type = EXCLUDED.authentication_type,
            status = 'installed',
            manifest = EXCLUDED.manifest,
            updated_at = now()
    """)
    for plugin in PLUGINS:
        connection.execute(statement, {**plugin, "manifest": json.dumps(plugin["manifest"], ensure_ascii=False)})


def downgrade() -> None:
    op.drop_table("plugin_connection_tests")
    op.drop_column("integration_credentials", "credential_fields")
    op.drop_column("company_plugins", "updated_at")
    op.drop_column("company_plugins", "created_at")
    op.execute("DELETE FROM plugins WHERE code IN ('imap_email', 'external_postgresql')")
