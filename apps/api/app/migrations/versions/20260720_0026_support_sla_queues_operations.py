"""Add support queues, SLA policies, events, and satisfaction.

Revision ID: 20260720_0026
Revises: 20260720_0025
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260720_0026"
down_revision: str | None = "20260720_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "support_queues",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("color", sa.String(length=20), server_default="#2f6f64", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "key", name="uq_support_queues_company_key"),
    )
    op.create_index("ix_support_queues_company_id", "support_queues", ["company_id"])
    op.create_index(
        "ix_support_queues_company_active", "support_queues", ["company_id", "is_active"]
    )

    op.create_table(
        "support_sla_policies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column(
            "targets",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "business_hours_only", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_support_sla_company_name"),
    )
    op.create_index("ix_support_sla_policies_company_id", "support_sla_policies", ["company_id"])

    op.add_column(
        "support_tickets", sa.Column("queue_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "support_tickets", sa.Column("sla_policy_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "support_tickets",
        sa.Column("first_response_due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "support_tickets", sa.Column("resolution_due_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "support_tickets",
        sa.Column("first_responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "support_tickets", sa.Column("breached_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("support_tickets", sa.Column("satisfaction_score", sa.Integer(), nullable=True))
    op.add_column("support_tickets", sa.Column("satisfaction_comment", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_support_tickets_queue",
        "support_tickets",
        "support_queues",
        ["queue_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_support_tickets_sla_policy",
        "support_tickets",
        "support_sla_policies",
        ["sla_policy_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_support_tickets_satisfaction",
        "support_tickets",
        "satisfaction_score IS NULL OR (satisfaction_score >= 1 AND satisfaction_score <= 5)",
    )
    for column in (
        "queue_id",
        "sla_policy_id",
        "first_response_due_at",
        "resolution_due_at",
        "breached_at",
    ):
        op.create_index(f"ix_support_tickets_{column}", "support_tickets", [column])

    op.create_table(
        "support_ticket_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "event_type IN ('created', 'assigned', 'queue_changed', 'priority_changed', 'status_changed', 'first_response', 'sla_breached', 'satisfaction_received')",
            name="ck_support_ticket_events_type",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_ticket_events_company_id", "support_ticket_events", ["company_id"])
    op.create_index("ix_support_ticket_events_ticket_id", "support_ticket_events", ["ticket_id"])
    op.create_index(
        "ix_support_ticket_events_actor_user_id", "support_ticket_events", ["actor_user_id"]
    )
    op.create_index("ix_support_ticket_events_created_at", "support_ticket_events", ["created_at"])
    op.create_index(
        "ix_support_ticket_events_company_ticket",
        "support_ticket_events",
        ["company_id", "ticket_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("support_ticket_events")
    for column in (
        "breached_at",
        "resolution_due_at",
        "first_response_due_at",
        "sla_policy_id",
        "queue_id",
    ):
        op.drop_index(f"ix_support_tickets_{column}", table_name="support_tickets")
    op.drop_constraint("ck_support_tickets_satisfaction", "support_tickets", type_="check")
    op.drop_constraint("fk_support_tickets_sla_policy", "support_tickets", type_="foreignkey")
    op.drop_constraint("fk_support_tickets_queue", "support_tickets", type_="foreignkey")
    for column in (
        "satisfaction_comment",
        "satisfaction_score",
        "breached_at",
        "first_responded_at",
        "resolution_due_at",
        "first_response_due_at",
        "sla_policy_id",
        "queue_id",
    ):
        op.drop_column("support_tickets", column)
    op.drop_table("support_sla_policies")
    op.drop_table("support_queues")
