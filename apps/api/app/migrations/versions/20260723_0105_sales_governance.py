"""sales territories, goals and governed renewals

Revision ID: 20260723_0105
Revises: 20260723_0104
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0105"
down_revision: str | None = "20260723_0104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_isolation ON "{table}"
        USING (
          company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid
        )
        WITH CHECK (
          company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid
        )
        """
    )


def upgrade() -> None:
    op.create_table(
        "crm_sales_territories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("region_code", sa.String(40), nullable=True),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_crm_sales_territories_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "name",
            name="uq_crm_sales_territories_company_name",
        ),
    )
    op.create_index(
        "ix_crm_sales_territories_company_id",
        "crm_sales_territories",
        ["company_id"],
    )

    op.add_column(
        "crm_opportunities",
        sa.Column(
            "territory_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_sales_territories.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_crm_opportunities_territory_id",
        "crm_opportunities",
        ["territory_id"],
    )

    op.create_table(
        "crm_sales_goals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "territory_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_sales_territories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("metric", sa.String(32), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("target_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "metric IN ('revenue', 'won_opportunities', 'new_accounts')",
            name="ck_crm_sales_goals_metric",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'completed', 'cancelled')",
            name="ck_crm_sales_goals_status",
        ),
        sa.CheckConstraint(
            "period_end >= period_start",
            name="ck_crm_sales_goals_period",
        ),
        sa.CheckConstraint(
            "target_value > 0",
            name="ck_crm_sales_goals_target",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_crm_sales_goals_company_id",
        "crm_sales_goals",
        ["company_id"],
    )
    op.create_index(
        "ix_crm_sales_goals_period",
        "crm_sales_goals",
        ["period_start", "period_end"],
    )

    op.create_table(
        "crm_renewal_plans",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "source_opportunity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_opportunities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("renewal_date", sa.Date(), nullable=False),
        sa.Column("expected_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("status", sa.String(16), server_default="planned", nullable=False),
        sa.Column("last_note", sa.String(1000), nullable=True),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'contacted', 'negotiating', 'renewed', 'lost')",
            name="ck_crm_renewal_plans_status",
        ),
        sa.CheckConstraint(
            "expected_amount >= 0",
            name="ck_crm_renewal_plans_amount",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_crm_renewal_plans_company_id",
        "crm_renewal_plans",
        ["company_id"],
    )
    op.create_index(
        "ix_crm_renewal_plans_date",
        "crm_renewal_plans",
        ["renewal_date"],
    )

    for table in (
        "crm_sales_territories",
        "crm_sales_goals",
        "crm_renewal_plans",
    ):
        _rls(table)


def downgrade() -> None:
    op.drop_table("crm_renewal_plans")
    op.drop_table("crm_sales_goals")
    op.drop_index(
        "ix_crm_opportunities_territory_id",
        table_name="crm_opportunities",
    )
    op.drop_column("crm_opportunities", "territory_id")
    op.drop_table("crm_sales_territories")
