"""Add managed vault connector catalog entries.

Revision ID: 20260721_0064
Revises: 20260721_0063
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0064"
down_revision: str | None = "20260721_0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VAULT_PLUGINS = (
    (
        "aws_secrets_manager",
        "AWS Secrets Manager",
        "Referências de chaves protegidas pelo AWS Secrets Manager com identidade gerenciada.",
        "aws-sm://",
    ),
    (
        "azure_key_vault",
        "Azure Key Vault",
        "Referências de chaves protegidas pelo Azure Key Vault com identidade gerenciada.",
        "azure-kv://",
    ),
    (
        "google_secret_manager",
        "Google Secret Manager",
        "Referências de chaves protegidas pelo Google Secret Manager com identidade gerenciada.",
        "gcp-sm://",
    ),
    (
        "hashicorp_vault",
        "HashiCorp Vault",
        "Referências de chaves protegidas pelo HashiCorp Vault sem tokens na URI.",
        "vault://",
    ),
)


def _manifest(provider: str, reference_prefix: str) -> dict[str, object]:
    return {
        "credential_fields": [
            {
                "key": "key_reference",
                "label": "Referência da chave",
                "kind": "password",
                "required": True,
                "secret": True,
                "placeholder": f"{reference_prefix}caminho/da/chave",
                "default": None,
            },
            {
                "key": "identity_reference",
                "label": "Identidade gerenciada ou papel",
                "kind": "text",
                "required": False,
                "secret": False,
                "placeholder": None,
                "default": None,
            },
        ],
        "configuration_fields": [],
        "tools": [],
        "triggers": [],
        "actions": [],
        "supports_token_refresh": False,
        "supports_webhooks": False,
        "vault_provider": provider,
        "reference_scheme": reference_prefix,
    }


def upgrade() -> None:
    connection = op.get_bind()
    statement = sa.text("""
        INSERT INTO plugins (code, name, version, description, authentication_type, status, manifest)
        VALUES (:code, :name, '1.0.0', :description, 'workload_identity', 'installed', CAST(:manifest AS jsonb))
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            version = EXCLUDED.version,
            description = EXCLUDED.description,
            authentication_type = EXCLUDED.authentication_type,
            status = 'installed',
            manifest = EXCLUDED.manifest,
            updated_at = now()
    """)
    for code, name, description, reference_prefix in VAULT_PLUGINS:
        connection.execute(
            statement,
            {
                "code": code,
                "name": name,
                "description": description,
                "manifest": json.dumps(_manifest(code, reference_prefix), ensure_ascii=False),
            },
        )


def downgrade() -> None:
    codes = ", ".join(f"'{code}'" for code, *_ in VAULT_PLUGINS)
    op.execute(f"UPDATE plugins SET status = 'disabled' WHERE code IN ({codes})")  # noqa: S608
