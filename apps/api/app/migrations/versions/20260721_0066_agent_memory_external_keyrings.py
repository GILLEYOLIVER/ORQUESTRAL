"""Activate tenant-scoped external keyrings for agent memory.

Revision ID: 20260721_0066
Revises: 20260721_0065
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0066"
down_revision: str | None = "20260721_0065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "agent_memory_keyring_bindings"
    op.create_table(
        table,
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "credential_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("integration_credentials.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider_code", sa.String(64), nullable=False),
        sa.Column("key_reference_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "activated_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "company_id",
            "agent_id",
            name="uq_agent_memory_keyring_binding_tenant_agent",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_agent_memory_keyring_binding_status",
        ),
        sa.CheckConstraint(
            "char_length(key_reference_fingerprint) = 64",
            name="ck_agent_memory_keyring_binding_reference",
        ),
    )
    for column in (
        "company_id",
        "agent_id",
        "credential_id",
        "provider_code",
        "status",
        "activated_by_user_id",
    ):
        op.create_index(f"ix_agent_memory_keyring_bindings_{column}", table, [column])


def downgrade() -> None:
    op.drop_table("agent_memory_keyring_bindings")
