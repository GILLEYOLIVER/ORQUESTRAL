"""governed external portals

Revision ID: 20260729_0120
Revises: 20260728_0119
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260729_0120"
down_revision: str | None = "20260728_0119"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
TABLES = ("portal_definitions", "portal_memberships", "portal_invitations")


def tenant() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
    ]


def protect(table: str) -> None:
    op.create_index(f"ix_{table}_company_id", table, ["company_id"])
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f"CREATE POLICY {table}_tenant_isolation ON {table} "
        "USING (company_id=NULLIF(current_setting('app.current_company_id',true),'')::uuid) "
        "WITH CHECK (company_id=NULLIF(current_setting('app.current_company_id',true),'')::uuid)"
    )


def upgrade() -> None:
    op.create_table(
        "portal_definitions",
        *tenant(),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("audience", sa.String(20), nullable=False),
        sa.Column("allowed_modules", sa.JSON(), nullable=False),
        sa.Column("branding", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "audience IN ('customer','partner','supplier','employee')",
            name="ck_portal_definitions_audience",
        ),
        sa.UniqueConstraint(
            "company_id", "code", name="uq_portal_definitions_company_code"
        ),
    )
    op.create_index(
        "ix_portal_definitions_company_active",
        "portal_definitions",
        ["company_id", "active"],
    )
    op.create_table(
        "portal_memberships",
        *tenant(),
        sa.Column(
            "portal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("portal_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "invited_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('invited','active','suspended','revoked')",
            name="ck_portal_memberships_status",
        ),
        sa.UniqueConstraint(
            "portal_id", "user_id", name="uq_portal_memberships_portal_user"
        ),
    )
    op.create_index(
        "ix_portal_memberships_company_status",
        "portal_memberships",
        ["company_id", "status"],
    )
    op.create_table(
        "portal_invitations",
        *tenant(),
        sa.Column(
            "membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("portal_memberships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("token_hash", name="uq_portal_invitations_token_hash"),
    )
    op.create_index(
        "ix_portal_invitations_company_expiry",
        "portal_invitations",
        ["company_id", "expires_at"],
    )
    for table in TABLES:
        protect(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
