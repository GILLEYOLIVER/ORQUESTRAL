"""Add isolated worker discovery for customer CDC retention.

Revision ID: 20260723_0099
Revises: 20260723_0098
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260723_0099"
down_revision: str | None = "20260723_0098"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "customer_cdc_retention_runs",
        "executed_by_user_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.add_column(
        "customer_cdc_retention_runs",
        sa.Column(
            "execution_source",
            sa.String(length=16),
            server_default="manual",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_customer_cdc_retention_execution_source",
        "customer_cdc_retention_runs",
        "execution_source IN ('manual', 'scheduled')",
    )
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION orkestral_cdc_retention_companies(
                requested_limit integer
            )
            RETURNS TABLE(company_id uuid)
            LANGUAGE sql
            SECURITY DEFINER
            SET search_path = public, pg_temp
            AS $function$
                WITH policies AS (
                    SELECT
                        subscription.company_id,
                        MIN(subscription.last_acknowledged_sequence)
                            AS cutoff_sequence,
                        MAX(subscription.retention_days) AS retention_days
                    FROM customer_cdc_subscriptions AS subscription
                    WHERE subscription.status = 'active'
                    GROUP BY subscription.company_id
                )
                SELECT policy.company_id
                FROM policies AS policy
                WHERE policy.cutoff_sequence > 0
                  AND EXISTS (
                      SELECT 1
                      FROM customer_change_events AS event
                      WHERE event.company_id = policy.company_id
                        AND event.sequence_number <= policy.cutoff_sequence
                        AND event.occurred_at < (
                            now() - make_interval(days => policy.retention_days)
                        )
                  )
                ORDER BY policy.company_id
                LIMIT GREATEST(1, LEAST(COALESCE(requested_limit, 100), 500))
            $function$
            """
        )
    )
    op.execute(
        sa.text(
            """
            REVOKE ALL ON FUNCTION
                orkestral_cdc_retention_companies(integer)
            FROM PUBLIC
            """
        )
    )
    op.execute(
        sa.text(
            """
            DO $block$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_roles WHERE rolname = 'orkestral_worker'
                ) THEN
                    GRANT EXECUTE ON FUNCTION
                        orkestral_cdc_retention_companies(integer)
                    TO orkestral_worker;
                END IF;
            END
            $block$
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DROP FUNCTION IF EXISTS
                orkestral_cdc_retention_companies(integer)
            """
        )
    )
    op.drop_constraint(
        "ck_customer_cdc_retention_execution_source",
        "customer_cdc_retention_runs",
        type_="check",
    )
    op.drop_column("customer_cdc_retention_runs", "execution_source")
    op.alter_column(
        "customer_cdc_retention_runs",
        "executed_by_user_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )

