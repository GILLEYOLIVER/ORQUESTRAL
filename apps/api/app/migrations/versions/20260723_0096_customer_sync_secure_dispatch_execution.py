"""Add secure execution outcomes and dispatch dead-letter handling.

Revision ID: 20260723_0096
Revises: 20260723_0095
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260723_0096"
down_revision: str | None = "20260723_0095"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME_ROLE = "orkestral_tenant_runtime"


def upgrade() -> None:
    op.drop_constraint(
        "ck_customer_sync_dispatch_status",
        "customer_sync_dispatches",
        type_="check",
    )
    op.create_check_constraint(
        "ck_customer_sync_dispatch_status",
        "customer_sync_dispatches",
        "status IN ('pending', 'claimed', 'acknowledged', 'failed', 'expired', 'dead_letter')",
    )
    op.add_column(
        "customer_sync_dispatches",
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "customer_sync_dispatches",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "customer_sync_dispatches",
        sa.Column("response_status_code", sa.Integer(), nullable=True),
    )
    op.add_column(
        "customer_sync_dispatches",
        sa.Column("response_bytes", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "customer_sync_dispatches",
        sa.Column("records_received", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "customer_sync_dispatches",
        sa.Column("result_fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_foreign_key(
        "fk_customer_sync_dispatch_run",
        "customer_sync_dispatches",
        "customer_sync_runs",
        ["run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_customer_sync_dispatch_response_status",
        "customer_sync_dispatches",
        "response_status_code IS NULL OR response_status_code BETWEEN 100 AND 599",
    )
    op.create_check_constraint(
        "ck_customer_sync_dispatch_response_bytes",
        "customer_sync_dispatches",
        "response_bytes BETWEEN 0 AND 1048576",
    )
    op.create_check_constraint(
        "ck_customer_sync_dispatch_records_received",
        "customer_sync_dispatches",
        "records_received BETWEEN 0 AND 100",
    )
    op.create_index(
        "ix_customer_sync_dispatch_claim_expiry",
        "customer_sync_dispatches",
        ["company_id", "status", "claim_expires_at"],
    )
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION public.orkestral_due_sync_dispatch_companies(
                requested_limit integer
            )
            RETURNS TABLE(company_id uuid)
            LANGUAGE sql
            SECURITY DEFINER
            SET search_path = pg_catalog, public
            AS $$
                SELECT DISTINCT dispatch.company_id
                FROM public.customer_sync_dispatches AS dispatch
                JOIN public.customer_sync_connectors AS connector
                  ON connector.company_id = dispatch.company_id
                 AND connector.id = dispatch.connector_id
                WHERE connector.status = 'active'
                  AND connector.adapter_key = 'generic_rest_pull'
                  AND dispatch.attempts < connector.max_attempts
                  AND (
                      (
                          dispatch.status IN ('pending', 'failed')
                          AND dispatch.available_at <= now()
                      )
                      OR (
                          dispatch.status = 'claimed'
                          AND dispatch.claim_expires_at <= now()
                      )
                  )
                ORDER BY dispatch.company_id
                LIMIT LEAST(GREATEST(requested_limit, 1), 500)
            $$
            """
        )
    )
    op.execute(
        sa.text(
            "REVOKE ALL ON FUNCTION "
            "public.orkestral_due_sync_dispatch_companies(integer) FROM PUBLIC"
        )
    )
    op.execute(
        sa.text(
            "GRANT EXECUTE ON FUNCTION "
            "public.orkestral_due_sync_dispatch_companies(integer) "
            f"TO {RUNTIME_ROLE}"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS "
            "public.orkestral_due_sync_dispatch_companies(integer)"
        )
    )
    op.drop_index(
        "ix_customer_sync_dispatch_claim_expiry",
        table_name="customer_sync_dispatches",
    )
    op.drop_constraint(
        "ck_customer_sync_dispatch_records_received",
        "customer_sync_dispatches",
        type_="check",
    )
    op.drop_constraint(
        "ck_customer_sync_dispatch_response_bytes",
        "customer_sync_dispatches",
        type_="check",
    )
    op.drop_constraint(
        "ck_customer_sync_dispatch_response_status",
        "customer_sync_dispatches",
        type_="check",
    )
    op.drop_constraint(
        "fk_customer_sync_dispatch_run",
        "customer_sync_dispatches",
        type_="foreignkey",
    )
    op.drop_column("customer_sync_dispatches", "result_fingerprint")
    op.drop_column("customer_sync_dispatches", "records_received")
    op.drop_column("customer_sync_dispatches", "response_bytes")
    op.drop_column("customer_sync_dispatches", "response_status_code")
    op.drop_column("customer_sync_dispatches", "run_id")
    op.drop_column("customer_sync_dispatches", "claim_expires_at")
    op.drop_constraint(
        "ck_customer_sync_dispatch_status",
        "customer_sync_dispatches",
        type_="check",
    )
    op.create_check_constraint(
        "ck_customer_sync_dispatch_status",
        "customer_sync_dispatches",
        "status IN ('pending', 'claimed', 'acknowledged', 'failed', 'expired')",
    )
