"""Add governed customer synchronization scheduling and observability.

Revision ID: 20260723_0094
Revises: 20260723_0093
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260723_0094"
down_revision: str | None = "20260723_0093"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME_ROLE = "orkestral_tenant_runtime"
READ_ONLY_ROLE = "orkestral_tenant_read_only"
TABLES = ("customer_sync_connectors", "customer_sync_runs")


def _uuid(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name,
        postgresql.UUID(as_uuid=True),
        nullable=nullable,
        server_default=sa.text("gen_random_uuid()") if name == "id" else None,
    )


def _tenant_rls(table_name: str, system_role: str) -> None:
    table = f"public.{table_name}"
    roles = f"{RUNTIME_ROLE}, {READ_ONLY_ROLE}"
    quoted_system_role = op.get_bind().dialect.identifier_preparer.quote(system_role)
    expression = "company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid"
    op.execute(sa.text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {RUNTIME_ROLE}"))
    op.execute(sa.text(f"GRANT SELECT ON {table} TO {READ_ONLY_ROLE}"))
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"CREATE POLICY orkestral_company_access ON {table} FOR ALL TO {roles} "
            f"USING ({expression}) WITH CHECK ({expression})"
        )
    )
    op.execute(
        sa.text(
            f"CREATE POLICY orkestral_system_access ON {table} FOR ALL "
            f"TO {quoted_system_role} USING (true) WITH CHECK (true)"
        )
    )
    op.execute(
        sa.text(
            f"CREATE POLICY orkestral_company_guard ON {table} AS RESTRICTIVE "
            f"FOR ALL TO {roles} USING ({expression}) WITH CHECK ({expression})"
        )
    )


def upgrade() -> None:
    op.create_table(
        "customer_sync_connectors",
        _uuid("id"),
        _uuid("company_id"),
        _uuid("source_id"),
        sa.Column("source_code", sa.String(length=80), nullable=False),
        sa.Column("transport", sa.String(length=20), nullable=False),
        _uuid("credential_binding_id", nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("schedule_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("base_backoff_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("lease_ttl_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("lease_token_hash", sa.String(length=64), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cursor", sa.String(length=500), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        _uuid("created_by_user_id"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["customer_data_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["credential_binding_id"],
            ["integration_credentials.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "source_code",
            name="uq_customer_sync_connector_source",
        ),
        sa.CheckConstraint(
            "transport IN ('push', 'pull', 'webhook')",
            name="ck_customer_sync_connector_transport",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'paused')",
            name="ck_customer_sync_connector_status",
        ),
        sa.CheckConstraint(
            "schedule_minutes BETWEEN 5 AND 10080",
            name="ck_customer_sync_connector_schedule",
        ),
        sa.CheckConstraint(
            "max_attempts BETWEEN 1 AND 10",
            name="ck_customer_sync_connector_attempts",
        ),
        sa.CheckConstraint(
            "base_backoff_seconds BETWEEN 5 AND 3600",
            name="ck_customer_sync_connector_backoff",
        ),
        sa.CheckConstraint(
            "lease_ttl_seconds BETWEEN 30 AND 3600",
            name="ck_customer_sync_connector_lease",
        ),
        sa.CheckConstraint(
            "consecutive_failures >= 0",
            name="ck_customer_sync_connector_failures",
        ),
    )
    op.create_index(
        "ix_customer_sync_connectors_due",
        "customer_sync_connectors",
        ["company_id", "status", "next_run_at"],
    )

    op.create_table(
        "customer_sync_runs",
        _uuid("id"),
        _uuid("company_id"),
        _uuid("connector_id"),
        _uuid("ingestion_job_id", nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("lease_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("cursor_before", sa.String(length=500), nullable=True),
        sa.Column("cursor_after", sa.String(length=500), nullable=True),
        sa.Column("total_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connector_id"],
            ["customer_sync_connectors.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_job_id"],
            ["customer_ingestion_jobs.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "connector_id",
            "idempotency_key",
            name="uq_customer_sync_run_idempotency",
        ),
        sa.CheckConstraint(
            "trigger IN ('manual', 'scheduled', 'webhook', 'retry')",
            name="ck_customer_sync_run_trigger",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'partial', 'failed')",
            name="ck_customer_sync_run_status",
        ),
        sa.CheckConstraint("attempt BETWEEN 1 AND 10", name="ck_customer_sync_run_attempt"),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_customer_sync_run_duration",
        ),
        sa.CheckConstraint(
            "total_records >= 0 AND accepted_records >= 0 AND rejected_records >= 0",
            name="ck_customer_sync_run_counts",
        ),
    )
    op.create_index(
        "ix_customer_sync_runs_company_created",
        "customer_sync_runs",
        ["company_id", "created_at"],
    )
    op.create_index(
        "ix_customer_sync_runs_connector_status",
        "customer_sync_runs",
        ["company_id", "connector_id", "status"],
    )

    system_role = str(op.get_bind().scalar(sa.text("SELECT current_user")))
    for table_name in TABLES:
        _tenant_rls(table_name, system_role)


def downgrade() -> None:
    op.drop_table("customer_sync_runs")
    op.drop_table("customer_sync_connectors")
