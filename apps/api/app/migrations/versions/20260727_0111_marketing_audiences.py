"""marketing reusable audiences

Revision ID: 20260727_0111
Revises: 20260727_0110
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260727_0111"
down_revision: str | None = "20260727_0110"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f"""CREATE POLICY {table}_tenant_isolation ON "{table}"
        USING (company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid)
        WITH CHECK (company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid)"""
    )


def upgrade() -> None:
    op.create_table(
        "marketing_audiences",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("segment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), server_default="draft", nullable=False),
        sa.Column("member_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("synchronized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('dynamic','static')", name="ck_marketing_audiences_kind"),
        sa.CheckConstraint("status IN ('draft','active','paused','archived')", name="ck_marketing_audiences_status"),
        sa.CheckConstraint("(kind = 'dynamic' AND segment_id IS NOT NULL) OR (kind = 'static' AND segment_id IS NULL)", name="ck_marketing_audiences_segment"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["segment_id"], ["customer_segments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "marketing_audience_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audience_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source IN ('segment','manual')", name="ck_marketing_audience_members_source"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["audience_id"], ["marketing_audiences.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["crm_contacts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audience_id", "contact_id", name="uq_marketing_audience_members_contact"),
    )
    for table, columns in {
        "marketing_audiences": ("company_id", "created_by_user_id", "segment_id", "name", "kind", "status", "archived_at"),
        "marketing_audience_members": ("company_id", "audience_id", "contact_id", "source"),
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])
        _rls(table)
    op.create_index(
        "ix_marketing_audiences_company_status",
        "marketing_audiences",
        ["company_id", "status"],
    )
    op.create_index(
        "ix_marketing_audience_members_company_audience",
        "marketing_audience_members",
        ["company_id", "audience_id"],
    )


def downgrade() -> None:
    for table in ("marketing_audience_members", "marketing_audiences"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.drop_table(table)
