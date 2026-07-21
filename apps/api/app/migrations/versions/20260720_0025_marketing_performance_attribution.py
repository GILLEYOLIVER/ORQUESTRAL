"""Add marketing performance, experiments, and revenue attribution.

Revision ID: 20260720_0025
Revises: 20260720_0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0025"
down_revision: str | None = "20260720_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "marketing_campaign_metrics",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
        sa.Column("channel", sa.String(length=30), server_default="multi_channel", nullable=False),
        sa.Column("variant_key", sa.String(length=80), server_default="all", nullable=False),
        sa.Column("impressions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reach", sa.Integer(), server_default="0", nullable=False),
        sa.Column("clicks", sa.Integer(), server_default="0", nullable=False),
        sa.Column("leads", sa.Integer(), server_default="0", nullable=False),
        sa.Column("conversions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("spend_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("revenue_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "impressions >= 0 AND reach >= 0 AND clicks >= 0 AND leads >= 0 AND conversions >= 0 AND spend_cents >= 0 AND revenue_cents >= 0",
            name="ck_marketing_campaign_metrics_nonnegative",
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["marketing_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campaign_id",
            "observed_on",
            "channel",
            "variant_key",
            name="uq_marketing_campaign_metric_slice",
        ),
    )
    op.create_index(
        "ix_marketing_campaign_metrics_campaign_id", "marketing_campaign_metrics", ["campaign_id"]
    )
    op.create_index(
        "ix_marketing_campaign_metrics_company_id", "marketing_campaign_metrics", ["company_id"]
    )
    op.create_index(
        "ix_marketing_campaign_metrics_observed_on", "marketing_campaign_metrics", ["observed_on"]
    )
    op.create_index(
        "ix_marketing_campaign_metrics_company_date",
        "marketing_campaign_metrics",
        ["company_id", "observed_on"],
    )

    op.create_table(
        "marketing_experiments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("success_metric", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("variants", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("winner_key", sa.String(length=80), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'running', 'completed', 'cancelled')",
            name="ck_marketing_experiments_status",
        ),
        sa.CheckConstraint(
            "success_metric IN ('click_rate', 'lead_rate', 'conversion_rate', 'revenue')",
            name="ck_marketing_experiments_metric",
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["marketing_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_marketing_experiments_campaign_id", "marketing_experiments", ["campaign_id"]
    )
    op.create_index("ix_marketing_experiments_company_id", "marketing_experiments", ["company_id"])
    op.create_index(
        "ix_marketing_experiments_company_status", "marketing_experiments", ["company_id", "status"]
    )

    op.create_table(
        "marketing_attributions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("touchpoint", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("medium", sa.String(length=120), nullable=True),
        sa.Column("value_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("value_cents >= 0", name="ck_marketing_attributions_value"),
        sa.CheckConstraint(
            "touchpoint IN ('first_touch', 'lead_creation', 'influenced', 'last_touch', 'conversion')",
            name="ck_marketing_attributions_touchpoint",
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["marketing_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["crm_contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["crm_opportunities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_marketing_attributions_campaign_id", "marketing_attributions", ["campaign_id"]
    )
    op.create_index(
        "ix_marketing_attributions_company_id", "marketing_attributions", ["company_id"]
    )
    op.create_index(
        "ix_marketing_attributions_contact_id", "marketing_attributions", ["contact_id"]
    )
    op.create_index(
        "ix_marketing_attributions_opportunity_id", "marketing_attributions", ["opportunity_id"]
    )
    op.create_index(
        "ix_marketing_attributions_company_campaign",
        "marketing_attributions",
        ["company_id", "campaign_id"],
    )


def downgrade() -> None:
    op.drop_table("marketing_attributions")
    op.drop_table("marketing_experiments")
    op.drop_table("marketing_campaign_metrics")
