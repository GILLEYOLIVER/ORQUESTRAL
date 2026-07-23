"""Add review and retry lineage for interrupted agent dispatches.

Revision ID: 20260722_0085
Revises: 20260722_0084
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260722_0085"
down_revision: str | None = "20260722_0084"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_agent_runtime_schedule_dispatch", "agent_runtime_dispatches", type_="unique"
    )
    op.drop_constraint(
        "uq_agent_runtime_event_dispatch", "agent_runtime_dispatches", type_="unique"
    )
    op.create_index(
        "uq_agent_runtime_schedule_dispatch_base",
        "agent_runtime_dispatches",
        ["schedule_id", "scheduled_for"],
        unique=True,
        postgresql_where=sa.text("source_type = 'schedule'"),
    )
    op.create_index(
        "uq_agent_runtime_event_dispatch_base",
        "agent_runtime_dispatches",
        ["trigger_id", "source_event_id"],
        unique=True,
        postgresql_where=sa.text("source_type = 'event'"),
    )
    op.drop_constraint(
        "ck_agent_runtime_dispatch_reference", "agent_runtime_dispatches", type_="check"
    )
    op.drop_constraint(
        "ck_agent_runtime_dispatch_source", "agent_runtime_dispatches", type_="check"
    )
    op.add_column(
        "agent_runtime_dispatches",
        sa.Column("retry_of_dispatch_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_runtime_dispatch_retry_of",
        "agent_runtime_dispatches",
        "agent_runtime_dispatches",
        ["retry_of_dispatch_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_agent_runtime_dispatches_retry_of_dispatch_id",
        "agent_runtime_dispatches",
        ["retry_of_dispatch_id"],
    )
    op.create_index(
        "ix_agent_runtime_dispatch_retry_lineage",
        "agent_runtime_dispatches",
        ["retry_of_dispatch_id", "created_at"],
    )
    op.create_check_constraint(
        "ck_agent_runtime_dispatch_source",
        "agent_runtime_dispatches",
        "source_type IN ('schedule', 'event', 'retry')",
    )
    op.create_check_constraint(
        "ck_agent_runtime_dispatch_reference",
        "agent_runtime_dispatches",
        "(source_type = 'schedule' AND schedule_id IS NOT NULL AND trigger_id IS NULL "
        "AND retry_of_dispatch_id IS NULL) OR "
        "(source_type = 'event' AND trigger_id IS NOT NULL AND schedule_id IS NULL "
        "AND source_event_id IS NOT NULL AND retry_of_dispatch_id IS NULL) OR "
        "(source_type = 'retry' AND retry_of_dispatch_id IS NOT NULL AND "
        "((schedule_id IS NOT NULL AND trigger_id IS NULL) OR "
        "(trigger_id IS NOT NULL AND schedule_id IS NULL AND source_event_id IS NOT NULL)))",
    )
    op.create_table(
        "agent_dispatch_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("interrupted_dispatch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("replacement_dispatch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("request_idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_idempotency_key", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("decision IN ('close', 'retry')", name="ck_agent_dispatch_review_decision"),
        sa.CheckConstraint(
            "status IN ('closed', 'pending_approval', 'approved')",
            name="ck_agent_dispatch_review_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["interrupted_dispatch_id"], ["agent_runtime_dispatches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["replacement_dispatch_id"], ["agent_runtime_dispatches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "interrupted_dispatch_id", name="uq_agent_dispatch_review_interrupted"),
        sa.UniqueConstraint("company_id", "request_idempotency_key", name="uq_agent_dispatch_review_request"),
        sa.UniqueConstraint("company_id", "approval_idempotency_key", name="uq_agent_dispatch_review_approval"),
        sa.UniqueConstraint("replacement_dispatch_id", name="uq_agent_dispatch_review_replacement"),
    )
    for column in (
        "company_id",
        "agent_id",
        "interrupted_dispatch_id",
        "replacement_dispatch_id",
        "request_idempotency_key",
        "approval_idempotency_key",
        "requested_by_user_id",
        "approved_by_user_id",
        "status",
    ):
        op.create_index(f"ix_agent_dispatch_reviews_{column}", "agent_dispatch_reviews", [column])
    op.create_index(
        "ix_agent_dispatch_review_queue",
        "agent_dispatch_reviews",
        ["company_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.execute("DELETE FROM agent_runtime_dispatches WHERE source_type = 'retry'")
    op.drop_table("agent_dispatch_reviews")
    op.drop_constraint(
        "ck_agent_runtime_dispatch_reference", "agent_runtime_dispatches", type_="check"
    )
    op.drop_constraint(
        "ck_agent_runtime_dispatch_source", "agent_runtime_dispatches", type_="check"
    )
    op.drop_index("ix_agent_runtime_dispatch_retry_lineage", table_name="agent_runtime_dispatches")
    op.drop_index(
        "ix_agent_runtime_dispatches_retry_of_dispatch_id", table_name="agent_runtime_dispatches"
    )
    op.drop_constraint(
        "fk_agent_runtime_dispatch_retry_of", "agent_runtime_dispatches", type_="foreignkey"
    )
    op.drop_column("agent_runtime_dispatches", "retry_of_dispatch_id")
    op.create_check_constraint(
        "ck_agent_runtime_dispatch_source",
        "agent_runtime_dispatches",
        "source_type IN ('schedule', 'event')",
    )
    op.create_check_constraint(
        "ck_agent_runtime_dispatch_reference",
        "agent_runtime_dispatches",
        "(source_type = 'schedule' AND schedule_id IS NOT NULL AND trigger_id IS NULL) OR "
        "(source_type = 'event' AND trigger_id IS NOT NULL AND schedule_id IS NULL "
        "AND source_event_id IS NOT NULL)",
    )
    op.drop_index("uq_agent_runtime_event_dispatch_base", table_name="agent_runtime_dispatches")
    op.drop_index("uq_agent_runtime_schedule_dispatch_base", table_name="agent_runtime_dispatches")
    op.create_unique_constraint(
        "uq_agent_runtime_event_dispatch",
        "agent_runtime_dispatches",
        ["trigger_id", "source_event_id"],
    )
    op.create_unique_constraint(
        "uq_agent_runtime_schedule_dispatch",
        "agent_runtime_dispatches",
        ["schedule_id", "scheduled_for"],
    )
