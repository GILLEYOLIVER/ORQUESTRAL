"""semantic analytics

Revision ID: 20260728_0118
Revises: 20260728_0117
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260728_0118"
down_revision: str | None = "20260728_0117"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "analytics_metric_definitions",
    "analytics_report_definitions",
    "analytics_dashboard_definitions",
    "analytics_report_runs",
)


def base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
    ]


def audit_columns() -> list[sa.Column]:
    return [
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
    ]


def rls(table: str) -> None:
    op.create_index(f"ix_{table}_company_id", table, ["company_id"])
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_isolation ON "{table}"
        USING (company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid)
        WITH CHECK (company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid)
        """
    )


def upgrade() -> None:
    op.create_table(
        "analytics_metric_definitions",
        *base_columns(),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("dataset", sa.String(80), nullable=False),
        sa.Column("aggregation", sa.String(12), nullable=False),
        sa.Column("value_field", sa.String(80)),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *audit_columns(),
        sa.CheckConstraint(
            "aggregation IN ('count','sum','avg','min','max')",
            name="ck_analytics_metric_definitions_aggregation",
        ),
        sa.UniqueConstraint(
            "company_id", "code", name="uq_analytics_metric_definitions_company_code"
        ),
    )
    op.create_index(
        "ix_analytics_metric_definitions_company_active",
        "analytics_metric_definitions",
        ["company_id", "active"],
    )
    op.create_table(
        "analytics_report_definitions",
        *base_columns(),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("dataset", sa.String(80), nullable=False),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("metric_codes", sa.JSON(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("visualization", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *audit_columns(),
        sa.CheckConstraint(
            "visualization IN ('table','bar','line','pie','kpi')",
            name="ck_analytics_report_definitions_visualization",
        ),
        sa.CheckConstraint(
            "status IN ('draft','published','archived')",
            name="ck_analytics_report_definitions_status",
        ),
    )
    op.create_index(
        "ix_analytics_report_definitions_company_status",
        "analytics_report_definitions",
        ["company_id", "status"],
    )
    op.create_table(
        "analytics_dashboard_definitions",
        *base_columns(),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("layout", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *audit_columns(),
        sa.UniqueConstraint(
            "company_id", "name", name="uq_analytics_dashboard_definitions_company_name"
        ),
    )
    op.create_index(
        "ix_analytics_dashboard_definitions_company_active",
        "analytics_dashboard_definitions",
        ["company_id", "active"],
    )
    op.create_table(
        "analytics_report_runs",
        *base_columns(),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analytics_report_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "executed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('completed','failed')", name="ck_analytics_report_runs_status"
        ),
    )
    op.create_index(
        "ix_analytics_report_runs_company_created",
        "analytics_report_runs",
        ["company_id", "created_at"],
    )
    for table in TABLES:
        rls(table)
    op.execute(
        "UPDATE modules_catalog SET version='2.0.0', updated_at=now() "
        "WHERE code='analytics'"
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute(
        "UPDATE modules_catalog SET version='1.0.0', updated_at=now() "
        "WHERE code='analytics'"
    )
