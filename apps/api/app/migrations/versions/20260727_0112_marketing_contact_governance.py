"""marketing contact governance

Revision ID: 20260727_0112
Revises: 20260727_0111
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260727_0112"
down_revision: str | None = "20260727_0111"
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
        "marketing_contact_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("timezone", sa.String(64), server_default="America/Sao_Paulo", nullable=False),
        sa.Column("allowed_weekdays", postgresql.JSONB(), server_default=sa.text("'[0,1,2,3,4]'::jsonb"), nullable=False),
        sa.Column("window_start", sa.Time(), server_default="08:00:00", nullable=False),
        sa.Column("window_end", sa.Time(), server_default="20:00:00", nullable=False),
        sa.Column("daily_limit", sa.Integer(), server_default="2", nullable=False),
        sa.Column("weekly_limit", sa.Integer(), server_default="5", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("channel IN ('email','whatsapp','sms','web')", name="ck_marketing_contact_policies_channel"),
        sa.CheckConstraint("daily_limit BETWEEN 1 AND 100 AND weekly_limit BETWEEN 1 AND 500", name="ck_marketing_contact_policies_limits"),
        sa.CheckConstraint("weekly_limit >= daily_limit", name="ck_marketing_contact_policies_limit_order"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "channel", name="uq_marketing_contact_policies_company_channel"),
    )
    op.create_table(
        "marketing_delivery_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("journey_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_snapshot", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("channel IN ('email','whatsapp','sms','web')", name="ck_marketing_delivery_attempts_channel"),
        sa.CheckConstraint("status IN ('reserved','sent','delivered','failed','blocked','cancelled')", name="ck_marketing_delivery_attempts_status"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["crm_contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["marketing_campaigns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["journey_id"], ["marketing_journeys.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_marketing_delivery_attempts_idempotency"),
    )
    for table, columns in {
        "marketing_contact_policies": ("company_id", "channel", "updated_by_user_id"),
        "marketing_delivery_attempts": ("company_id", "contact_id", "campaign_id", "journey_id", "channel", "status", "reason_code", "scheduled_for", "created_by_user_id", "created_at"),
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])
        _rls(table)
    op.create_index("ix_marketing_delivery_attempts_frequency", "marketing_delivery_attempts", ["company_id", "contact_id", "channel", "created_at"])


def downgrade() -> None:
    for table in ("marketing_delivery_attempts", "marketing_contact_policies"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.drop_table(table)
