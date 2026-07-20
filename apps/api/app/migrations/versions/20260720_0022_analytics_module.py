"""Instala indicadores, metas e medicoes do Analytics.

Revision ID: 20260720_0022
Revises: 20260720_0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0022"
down_revision: str | None = "20260720_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analytics_indicators",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=80), server_default="Geral", nullable=False),
        sa.Column("unit", sa.String(length=20), server_default="number", nullable=False),
        sa.Column(
            "direction", sa.String(length=24), server_default="higher_better", nullable=False
        ),
        sa.Column("target_value", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "direction IN ('higher_better','lower_better','neutral')",
            name="ck_analytics_indicators_direction",
        ),
        sa.CheckConstraint(
            "unit IN ('number','currency','percent','hours','days')",
            name="ck_analytics_indicators_unit",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "code", name="uq_analytics_indicators_company_code"),
    )
    op.create_index(
        "ix_analytics_indicators_company_active",
        "analytics_indicators",
        ["company_id", "active"],
    )
    op.create_index("ix_analytics_indicators_company_id", "analytics_indicators", ["company_id"])
    op.create_index("ix_analytics_indicators_created_at", "analytics_indicators", ["created_at"])
    op.create_table(
        "analytics_measurements",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("indicator_id", sa.Uuid(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("source", sa.String(length=80), server_default="manual", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("period_end >= period_start", name="ck_analytics_measurements_period"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["indicator_id"], ["analytics_indicators.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "indicator_id",
            "period_start",
            "period_end",
            name="uq_analytics_measurements_indicator_period",
        ),
    )
    op.create_index(
        "ix_analytics_measurements_company_id", "analytics_measurements", ["company_id"]
    )
    op.create_index(
        "ix_analytics_measurements_company_period",
        "analytics_measurements",
        ["company_id", "period_end"],
    )
    op.create_index(
        "ix_analytics_measurements_created_at", "analytics_measurements", ["created_at"]
    )
    op.create_index(
        "ix_analytics_measurements_indicator_id", "analytics_measurements", ["indicator_id"]
    )
    op.create_index(
        "ix_analytics_measurements_period_end", "analytics_measurements", ["period_end"]
    )
    op.create_index(
        "ix_analytics_measurements_recorded_by_user_id",
        "analytics_measurements",
        ["recorded_by_user_id"],
    )


def downgrade() -> None:
    op.drop_table("analytics_measurements")
    op.drop_table("analytics_indicators")
