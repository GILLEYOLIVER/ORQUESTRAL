"""support sla escalation calendar

Revision ID: 20260727_0108
Revises: 20260723_0107
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260727_0108"
down_revision: str | None = "20260723_0107"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_isolation ON "{table}"
        USING (
            company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid
        )
        WITH CHECK (
            company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid
        )
        """
    )


def upgrade() -> None:
    op.create_table(
        "support_business_calendars",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "timezone",
            sa.String(length=80),
            server_default="America/Sao_Paulo",
            nullable=False,
        ),
        sa.Column(
            "weekly_schedule",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "holidays",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "name",
            name="uq_support_business_calendars_company_name",
        ),
    )
    for column in (
        "company_id",
        "created_by_user_id",
        "updated_by_user_id",
        "is_active",
        "created_at",
    ):
        op.create_index(
            f"ix_support_business_calendars_{column}",
            "support_business_calendars",
            [column],
        )

    op.create_table(
        "support_escalation_policies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sla_policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("calendar_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("escalation_queue_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("escalation_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "warning_minutes_before",
            sa.Integer(),
            server_default="30",
            nullable=False,
        ),
        sa.Column("action", sa.String(length=24), server_default="notify", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
            "action IN ('notify', 'prioritize', 'reassign_queue', 'reassign_user')",
            name="ck_support_escalation_policies_action",
        ),
        sa.CheckConstraint(
            "warning_minutes_before BETWEEN 0 AND 10080",
            name="ck_support_escalation_policies_warning",
        ),
        sa.CheckConstraint(
            "(action <> 'reassign_queue' OR escalation_queue_id IS NOT NULL) AND "
            "(action <> 'reassign_user' OR escalation_user_id IS NOT NULL)",
            name="ck_support_escalation_policies_target",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["sla_policy_id"], ["support_sla_policies.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["calendar_id"], ["support_business_calendars.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["escalation_queue_id"], ["support_queues.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["escalation_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "name",
            name="uq_support_escalation_policies_company_name",
        ),
    )
    for column in (
        "company_id",
        "sla_policy_id",
        "calendar_id",
        "escalation_queue_id",
        "escalation_user_id",
        "created_by_user_id",
        "action",
        "is_active",
        "created_at",
    ):
        op.create_index(
            f"ix_support_escalation_policies_{column}",
            "support_escalation_policies",
            [column],
        )

    op.create_table(
        "support_escalation_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="applied", nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('warning', 'breach')",
            name="ck_support_escalation_events_kind",
        ),
        sa.CheckConstraint(
            "status IN ('applied', 'skipped')",
            name="ck_support_escalation_events_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"], ["support_escalation_policies.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "ticket_id",
            "policy_id",
            "kind",
            "deadline_at",
            name="uq_support_escalation_events_idempotency",
        ),
    )
    for column in (
        "company_id",
        "ticket_id",
        "policy_id",
        "kind",
        "status",
        "deadline_at",
        "occurred_at",
    ):
        op.create_index(
            f"ix_support_escalation_events_{column}",
            "support_escalation_events",
            [column],
        )

    for table in (
        "support_business_calendars",
        "support_escalation_policies",
        "support_escalation_events",
    ):
        _rls(table)


def downgrade() -> None:
    for table in (
        "support_escalation_events",
        "support_escalation_policies",
        "support_business_calendars",
    ):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.drop_table(table)
