"""Add customer sync adapter registry, scheduler queue and health checks.

Revision ID: 20260723_0095
Revises: 20260723_0094
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260723_0095"
down_revision: str | None = "20260723_0094"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME_ROLE = "orkestral_tenant_runtime"
READ_ONLY_ROLE = "orkestral_tenant_read_only"
TABLES = ("customer_sync_adapter_health_checks", "customer_sync_dispatches")


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
    op.add_column(
        "customer_sync_connectors",
        sa.Column(
            "adapter_key",
            sa.String(length=80),
            nullable=False,
            server_default="secure_push",
        ),
    )
    op.add_column(
        "customer_sync_connectors",
        sa.Column(
            "adapter_version",
            sa.String(length=32),
            nullable=False,
            server_default="1.0.0",
        ),
    )
    op.create_check_constraint(
        "ck_customer_sync_connector_adapter_key",
        "customer_sync_connectors",
        "adapter_key ~ '^[a-z][a-z0-9._-]{1,79}$'",
    )

    op.create_table(
        "customer_sync_adapter_health_checks",
        _uuid("id"),
        _uuid("company_id"),
        _uuid("connector_id"),
        sa.Column("adapter_key", sa.String(length=80), nullable=False),
        sa.Column("adapter_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "checked_at",
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
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('ready', 'unverified', 'degraded', 'blocked')",
            name="ck_customer_sync_adapter_health_status",
        ),
        sa.CheckConstraint("latency_ms >= 0", name="ck_customer_sync_adapter_health_latency"),
    )
    op.create_index(
        "ix_customer_sync_adapter_health_latest",
        "customer_sync_adapter_health_checks",
        ["company_id", "connector_id", "checked_at"],
    )

    op.create_table(
        "customer_sync_dispatches",
        _uuid("id"),
        _uuid("company_id"),
        _uuid("connector_id"),
        sa.Column("adapter_key", sa.String(length=80), nullable=False),
        sa.Column("adapter_version", sa.String(length=32), nullable=False),
        sa.Column("schedule_slot", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("scheduler_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("claim_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connector_id"],
            ["customer_sync_connectors.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "connector_id",
            "schedule_slot",
            name="uq_customer_sync_dispatch_schedule",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'claimed', 'acknowledged', 'failed', 'expired')",
            name="ck_customer_sync_dispatch_status",
        ),
        sa.CheckConstraint(
            "attempts BETWEEN 0 AND 10",
            name="ck_customer_sync_dispatch_attempts",
        ),
    )
    op.create_index(
        "ix_customer_sync_dispatches_available",
        "customer_sync_dispatches",
        ["company_id", "status", "available_at"],
    )

    system_role = str(op.get_bind().scalar(sa.text("SELECT current_user")))
    for table_name in TABLES:
        _tenant_rls(table_name, system_role)

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION public.orkestral_due_sync_companies(
                requested_limit integer
            )
            RETURNS TABLE(company_id uuid)
            LANGUAGE sql
            SECURITY DEFINER
            SET search_path = pg_catalog, public
            AS $$
                SELECT DISTINCT connector.company_id
                FROM public.customer_sync_connectors AS connector
                WHERE connector.status = 'active'
                  AND connector.next_run_at IS NOT NULL
                  AND connector.next_run_at <= now()
                  AND (connector.lease_until IS NULL OR connector.lease_until <= now())
                ORDER BY connector.company_id
                LIMIT LEAST(GREATEST(requested_limit, 1), 500)
            $$
            """
        )
    )
    op.execute(
        sa.text("REVOKE ALL ON FUNCTION public.orkestral_due_sync_companies(integer) FROM PUBLIC")
    )
    op.execute(
        sa.text(
            "GRANT EXECUTE ON FUNCTION public.orkestral_due_sync_companies(integer) "
            f"TO {RUNTIME_ROLE}"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP FUNCTION IF EXISTS public.orkestral_due_sync_companies(integer)"))
    op.drop_table("customer_sync_dispatches")
    op.drop_table("customer_sync_adapter_health_checks")
    op.drop_constraint(
        "ck_customer_sync_connector_adapter_key",
        "customer_sync_connectors",
        type_="check",
    )
    op.drop_column("customer_sync_connectors", "adapter_version")
    op.drop_column("customer_sync_connectors", "adapter_key")
