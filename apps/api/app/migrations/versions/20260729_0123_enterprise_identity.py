"""enterprise identity and SCIM

Revision ID: 20260729_0123
Revises: 20260729_0122
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260729_0123"
down_revision: str | None = "20260729_0122"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
TABLES = ("enterprise_identity_providers", "scim_provisioning_tokens")


def _protect(table: str) -> None:
    op.create_index(f"ix_{table}_company_id", table, ["company_id"])
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')


def upgrade() -> None:
    op.create_table(
        "enterprise_identity_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("provider_type", sa.String(20), nullable=False),
        sa.Column("issuer", sa.String(500), nullable=False),
        sa.Column("client_id", sa.String(255)),
        sa.Column("encrypted_client_secret", sa.LargeBinary()),
        sa.Column("authorization_endpoint", sa.String(500)),
        sa.Column("token_endpoint", sa.String(500)),
        sa.Column("jwks_uri", sa.String(500)),
        sa.Column("metadata_url", sa.String(500)),
        sa.Column("allowed_domains", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("status", sa.String(20), server_default="configured", nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("provider_type IN ('oidc', 'saml')", name="ck_enterprise_identity_providers_type"),
        sa.CheckConstraint("status IN ('configured', 'active', 'disabled', 'error')", name="ck_enterprise_identity_providers_status"),
        sa.UniqueConstraint("company_id", "code", name="uq_enterprise_identity_providers_company_code"),
    )
    op.create_index("ix_enterprise_identity_providers_created_by_user_id", "enterprise_identity_providers", ["created_by_user_id"])
    _protect("enterprise_identity_providers")
    op.create_table(
        "scim_provisioning_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("scopes", postgresql.JSONB(), nullable=False),
        sa.Column("default_role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('active', 'revoked', 'expired')", name="ck_scim_provisioning_tokens_status"),
    )
    for column in ("default_role_id", "expires_at", "created_by_user_id"):
        op.create_index(f"ix_scim_provisioning_tokens_{column}", "scim_provisioning_tokens", [column])
    _protect("scim_provisioning_tokens")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
