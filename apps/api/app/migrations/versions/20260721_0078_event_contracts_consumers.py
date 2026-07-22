"""Add governed event contracts, subscriptions and idempotent deliveries.

Revision ID: 20260721_0078
Revises: 20260721_0077
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0078"
down_revision: str | None = "20260721_0077"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_contracts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=160), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column(
            "classification", sa.String(length=24), server_default="internal", nullable=False
        ),
        sa.Column(
            "compatibility_mode", sa.String(length=20), server_default="backward", nullable=False
        ),
        sa.Column("payload_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("published_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("version >= 1", name="ck_event_contract_version"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'retired')", name="ck_event_contract_status"
        ),
        sa.CheckConstraint(
            "classification IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_event_contract_classification",
        ),
        sa.CheckConstraint(
            "compatibility_mode IN ('strict', 'backward')", name="ck_event_contract_compatibility"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "event_type", "version", name="uq_event_contract_company_type_version"
        ),
    )
    op.create_index("ix_event_contracts_company_id", "event_contracts", ["company_id"])
    op.create_index("ix_event_contracts_event_type", "event_contracts", ["event_type"])
    op.create_index(
        "ix_event_contract_company_type_status",
        "event_contracts",
        ["company_id", "event_type", "status"],
    )

    op.create_table(
        "event_subscriptions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("consumer_name", sa.String(length=160), nullable=False),
        sa.Column("event_type", sa.String(length=160), nullable=False),
        sa.Column("min_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("max_version", sa.Integer(), nullable=True),
        sa.Column("delivery_mode", sa.String(length=20), server_default="ledger", nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="8", nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("min_version >= 1", name="ck_event_subscription_min_version"),
        sa.CheckConstraint(
            "max_version IS NULL OR max_version >= min_version",
            name="ck_event_subscription_version_range",
        ),
        sa.CheckConstraint(
            "delivery_mode IN ('ledger', 'workflow')", name="ck_event_subscription_delivery_mode"
        ),
        sa.CheckConstraint(
            "(delivery_mode = 'workflow' AND workflow_id IS NOT NULL) OR (delivery_mode = 'ledger' AND workflow_id IS NULL)",
            name="ck_event_subscription_workflow_binding",
        ),
        sa.CheckConstraint(
            "max_attempts BETWEEN 1 AND 25", name="ck_event_subscription_max_attempts"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "consumer_name", "event_type", name="uq_event_subscription_consumer_type"
        ),
    )
    op.create_index("ix_event_subscriptions_company_id", "event_subscriptions", ["company_id"])
    op.create_index("ix_event_subscriptions_event_type", "event_subscriptions", ["event_type"])
    op.create_index("ix_event_subscriptions_workflow_id", "event_subscriptions", ["workflow_id"])
    op.create_index(
        "ix_event_subscription_match", "event_subscriptions", ["company_id", "event_type", "active"]
    )

    op.create_table(
        "event_deliveries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="8", nullable=False),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=120), nullable=True),
        sa.Column("last_error_code", sa.String(length=120), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replay_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'succeeded', 'failed', 'dead_letter')",
            name="ck_event_delivery_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_event_delivery_attempts"),
        sa.CheckConstraint("max_attempts BETWEEN 1 AND 25", name="ck_event_delivery_max_attempts"),
        sa.CheckConstraint("replay_count >= 0", name="ck_event_delivery_replay_count"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["outbox_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["event_subscriptions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id", "subscription_id", name="uq_event_delivery_event_subscription"
        ),
    )
    op.create_index("ix_event_deliveries_company_id", "event_deliveries", ["company_id"])
    op.create_index("ix_event_deliveries_event_id", "event_deliveries", ["event_id"])
    op.create_index("ix_event_deliveries_subscription_id", "event_deliveries", ["subscription_id"])
    op.create_index("ix_event_deliveries_available_at", "event_deliveries", ["available_at"])
    op.create_index(
        "ix_event_delivery_dispatch", "event_deliveries", ["status", "available_at", "locked_at"]
    )
    op.create_index(
        "ix_event_delivery_company_status",
        "event_deliveries",
        ["company_id", "status", "created_at"],
    )

    op.add_column(
        "workflow_executions",
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_workflow_execution_source_event",
        "workflow_executions",
        "outbox_events",
        ["source_event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_workflow_executions_source_event_id", "workflow_executions", ["source_event_id"]
    )
    op.create_unique_constraint(
        "uq_workflow_execution_event",
        "workflow_executions",
        ["company_id", "workflow_id", "source_event_id"],
    )
    op.drop_constraint("ck_workflow_executions_source", "workflow_executions", type_="check")
    op.create_check_constraint(
        "ck_workflow_executions_source",
        "workflow_executions",
        "source IN ('manual', 'webhook', 'schedule', 'system', 'domain_event')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_workflow_executions_source", "workflow_executions", type_="check")
    op.create_check_constraint(
        "ck_workflow_executions_source",
        "workflow_executions",
        "source IN ('manual', 'webhook', 'schedule', 'system')",
    )
    op.drop_constraint("uq_workflow_execution_event", "workflow_executions", type_="unique")
    op.drop_index("ix_workflow_executions_source_event_id", table_name="workflow_executions")
    op.drop_constraint(
        "fk_workflow_execution_source_event", "workflow_executions", type_="foreignkey"
    )
    op.drop_column("workflow_executions", "source_event_id")
    op.drop_table("event_deliveries")
    op.drop_table("event_subscriptions")
    op.drop_table("event_contracts")
