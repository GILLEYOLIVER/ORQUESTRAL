"""support omnichannel ingress

Revision ID: 20260723_0107
Revises: 20260723_0106
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260723_0107"
down_revision: str | None = "20260723_0106"
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
        "support_channel_endpoints",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("default_queue_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("public_key", sa.String(length=120), nullable=False),
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.Column("secret_fingerprint", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "default_priority",
            sa.String(length=20),
            server_default=sa.text("'normal'"),
            nullable=False,
        ),
        sa.Column(
            "consent_required",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("last_received_at", sa.DateTime(timezone=True), nullable=True),
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
            "channel IN ('email', 'chat', 'whatsapp', 'form', 'portal')",
            name="ck_support_channel_endpoints_channel",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'revoked')",
            name="ck_support_channel_endpoints_status",
        ),
        sa.CheckConstraint(
            "default_priority IN ('low', 'normal', 'high', 'urgent')",
            name="ck_support_channel_endpoints_priority",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["default_queue_id"],
            ["support_queues.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_key"),
        sa.UniqueConstraint(
            "company_id",
            "channel",
            "name",
            name="uq_support_channel_endpoints_company_channel_name",
        ),
    )
    for index in (
        "company_id",
        "created_by_user_id",
        "updated_by_user_id",
        "default_queue_id",
        "channel",
        "public_key",
        "status",
        "created_at",
    ):
        op.create_index(
            f"ix_support_channel_endpoints_{index}",
            "support_channel_endpoints",
            [index],
        )

    op.create_table(
        "support_channel_ingress_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_event_id", sa.String(length=160), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("sender_reference_hash", sa.String(length=64), nullable=True),
        sa.Column("source_ip_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=24),
            server_default=sa.text("'ticket_created'"),
            nullable=False,
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ticket_created', 'rejected')",
            name="ck_support_channel_ingress_events_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["endpoint_id"],
            ["support_channel_endpoints.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["support_tickets.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "endpoint_id",
            "external_event_id",
            name="uq_support_channel_ingress_events_endpoint_external",
        ),
    )
    for index in (
        "company_id",
        "endpoint_id",
        "ticket_id",
        "status",
        "received_at",
    ):
        op.create_index(
            f"ix_support_channel_ingress_events_{index}",
            "support_channel_ingress_events",
            [index],
        )

    _rls("support_channel_endpoints")
    _rls("support_channel_ingress_events")


def downgrade() -> None:
    for table in ("support_channel_ingress_events", "support_channel_endpoints"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.drop_table("support_channel_ingress_events")
    op.drop_table("support_channel_endpoints")
