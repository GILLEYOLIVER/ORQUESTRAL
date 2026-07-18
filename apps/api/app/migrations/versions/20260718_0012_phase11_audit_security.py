"""Auditoria e seguranca transversal.

Revision ID: 20260718_0012
Revises: 20260718_0011
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260718_0012"
down_revision: str | None = "20260718_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", UUID, nullable=True),
        sa.Column("actor_user_id", UUID, nullable=True),
        sa.Column("actor_type", sa.String(20), server_default="user", nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(120), nullable=False),
        sa.Column("resource_id", sa.String(120), nullable=True),
        sa.Column("before_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("created_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('user','system','service','anonymous')",
            name="ck_audit_events_actor_type",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "actor_user_id",
        "action",
        "resource_type",
        "resource_id",
        "request_id",
        "created_at",
    ):
        op.create_index(f"ix_audit_events_{column}", "audit_events", [column])
    op.create_index(
        "ix_audit_events_company_created",
        "audit_events",
        ["company_id", "created_at"],
    )
    op.execute(
        """
        INSERT INTO permissions (id, code, module_code, action, description)
        VALUES (gen_random_uuid(), 'audit.view', 'audit', 'view', 'Consultar eventos de auditoria')
        ON CONFLICT (code) DO UPDATE SET
            module_code = EXCLUDED.module_code,
            action = EXCLUDED.action,
            description = EXCLUDED.description
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code = 'audit.view'")
    op.drop_table("audit_events")
