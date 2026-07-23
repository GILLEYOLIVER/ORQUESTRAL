"""Add safe customer CDC retention audit runs.

Revision ID: 20260723_0098
Revises: 20260723_0097
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260723_0098"
down_revision: str | None = "20260723_0097"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_cdc_retention_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cutoff_sequence", sa.BigInteger(), nullable=False),
        sa.Column("effective_retention_days", sa.Integer(), nullable=False),
        sa.Column("eligible_events", sa.Integer(), nullable=False),
        sa.Column("deleted_events", sa.Integer(), nullable=False),
        sa.Column("max_delete", sa.Integer(), nullable=False),
        sa.Column(
            "executed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "cutoff_sequence >= 0",
            name="ck_customer_cdc_retention_cutoff",
        ),
        sa.CheckConstraint(
            "effective_retention_days >= 0",
            name="ck_customer_cdc_retention_days",
        ),
        sa.CheckConstraint(
            "eligible_events >= deleted_events AND deleted_events >= 0",
            name="ck_customer_cdc_retention_counts",
        ),
        sa.CheckConstraint(
            "max_delete BETWEEN 1 AND 5000",
            name="ck_customer_cdc_retention_max_delete",
        ),
    )
    op.create_index(
        "ix_customer_cdc_retention_company_executed",
        "customer_cdc_retention_runs",
        ["company_id", "executed_at"],
    )
    op.execute(
        sa.text("ALTER TABLE customer_cdc_retention_runs ENABLE ROW LEVEL SECURITY")
    )
    op.execute(
        sa.text(
            """
            CREATE POLICY customer_cdc_retention_runs_tenant_isolation
            ON customer_cdc_retention_runs
            USING (
                company_id = NULLIF(
                    current_setting('app.current_company_id', true),
                    ''
                )::uuid
            )
            WITH CHECK (
                company_id = NULLIF(
                    current_setting('app.current_company_id', true),
                    ''
                )::uuid
            )
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DROP POLICY IF EXISTS customer_cdc_retention_runs_tenant_isolation
            ON customer_cdc_retention_runs
            """
        )
    )
    op.drop_index(
        "ix_customer_cdc_retention_company_executed",
        table_name="customer_cdc_retention_runs",
    )
    op.drop_table("customer_cdc_retention_runs")

