"""Dashboards, resumos diarios e agregacoes.

Revision ID: 20260718_0011
Revises: 20260718_0010
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260718_0011"
down_revision: str | None = "20260718_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "metric_daily_summaries",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("module", sa.String(40), nullable=False),
        sa.Column("metric_key", sa.String(80), nullable=False),
        sa.Column("agent_id", UUID, nullable=True),
        sa.Column("workflow_id", UUID, nullable=True),
        sa.Column("count_value", sa.Integer(), server_default="0", nullable=False),
        sa.Column("numeric_value", sa.Numeric(20, 6), server_default="0", nullable=False),
        sa.Column("generated_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("count_value >= 0", name="ck_metric_daily_summaries_count"),
        sa.CheckConstraint("numeric_value >= 0", name="ck_metric_daily_summaries_numeric"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("company_id", "metric_date", "module", "metric_key", "agent_id", "workflow_id", "generated_at"):
        op.create_index(f"ix_metric_daily_summaries_{column}", "metric_daily_summaries", [column])

    op.create_table(
        "metric_aggregation_runs",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("status", sa.String(20), server_default="running", nullable=False),
        sa.Column("rows_written", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", TIMESTAMP, nullable=True),
        sa.CheckConstraint("status IN ('running','success','error')", name="ck_metric_aggregation_runs_status"),
        sa.CheckConstraint("rows_written >= 0", name="ck_metric_aggregation_runs_rows"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_metric_aggregation_runs_status", "metric_aggregation_runs", ["status"])
    op.create_index("ix_metric_aggregation_runs_started_at", "metric_aggregation_runs", ["started_at"])


def downgrade() -> None:
    op.drop_table("metric_aggregation_runs")
    op.drop_table("metric_daily_summaries")
