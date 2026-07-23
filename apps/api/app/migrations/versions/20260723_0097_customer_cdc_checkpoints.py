"""Add governed customer CDC events and checkpoints.

Revision ID: 20260723_0097
Revises: 20260723_0096
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260723_0097"
down_revision: str | None = "20260723_0096"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_tenant_rls(table_name: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY {table_name}_tenant_isolation
            ON {table_name}
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


def upgrade() -> None:
    op.create_table(
        "customer_cdc_counters",
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("next_sequence", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "next_sequence >= 1",
            name="ck_customer_cdc_counters_next_sequence",
        ),
    )
    op.create_table(
        "customer_change_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.BigInteger(), nullable=False),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("operation", sa.String(length=24), nullable=False),
        sa.Column(
            "changed_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_data_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "ingestion_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_ingestion_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_record_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "operation IN ('upserted', 'merged', 'deleted')",
            name="ck_customer_change_events_operation",
        ),
        sa.UniqueConstraint(
            "company_id",
            "sequence_number",
            name="uq_customer_change_events_company_sequence",
        ),
        sa.UniqueConstraint(
            "company_id",
            "source_id",
            "profile_id",
            "payload_fingerprint",
            name="uq_customer_change_events_payload",
        ),
    )
    op.create_index(
        "ix_customer_change_events_company_occurred",
        "customer_change_events",
        ["company_id", "occurred_at"],
    )
    op.create_table(
        "customer_cdc_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("consumer_key", sa.String(length=80), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "operations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("batch_size", sa.Integer(), server_default="50", nullable=False),
        sa.Column(
            "retention_days",
            sa.Integer(),
            server_default="30",
            nullable=False,
        ),
        sa.Column(
            "last_acknowledged_sequence",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
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
            "status IN ('active', 'paused')",
            name="ck_customer_cdc_subscriptions_status",
        ),
        sa.CheckConstraint(
            "batch_size BETWEEN 1 AND 200",
            name="ck_customer_cdc_subscriptions_batch_size",
        ),
        sa.CheckConstraint(
            "retention_days BETWEEN 1 AND 365",
            name="ck_customer_cdc_subscriptions_retention_days",
        ),
        sa.UniqueConstraint(
            "company_id",
            "consumer_key",
            name="customer_cdc_subscriptions_company_consumer_key_key",
        ),
    )
    op.create_table(
        "customer_cdc_checkpoint_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_cdc_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("previous_sequence", sa.BigInteger(), nullable=False),
        sa.Column("acknowledged_sequence", sa.BigInteger(), nullable=False),
        sa.Column(
            "acknowledged_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "acknowledged_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "acknowledged_sequence > previous_sequence",
            name="ck_customer_cdc_checkpoint_monotonic",
        ),
    )
    op.create_index(
        "ix_customer_cdc_checkpoint_subscription",
        "customer_cdc_checkpoint_history",
        ["company_id", "subscription_id", "acknowledged_at"],
    )

    for table_name in (
        "customer_cdc_counters",
        "customer_change_events",
        "customer_cdc_subscriptions",
        "customer_cdc_checkpoint_history",
    ):
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    for table_name in (
        "customer_cdc_checkpoint_history",
        "customer_cdc_subscriptions",
        "customer_change_events",
        "customer_cdc_counters",
    ):
        op.execute(
            sa.text(
                f"DROP POLICY IF EXISTS {table_name}_tenant_isolation ON {table_name}"
            )
        )
    op.drop_index(
        "ix_customer_cdc_checkpoint_subscription",
        table_name="customer_cdc_checkpoint_history",
    )
    op.drop_table("customer_cdc_checkpoint_history")
    op.drop_table("customer_cdc_subscriptions")
    op.drop_index(
        "ix_customer_change_events_company_occurred",
        table_name="customer_change_events",
    )
    op.drop_table("customer_change_events")
    op.drop_table("customer_cdc_counters")

