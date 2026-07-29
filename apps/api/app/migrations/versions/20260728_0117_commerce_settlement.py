"""commerce settlement

Revision ID: 20260728_0117
Revises: 20260728_0116
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260728_0117"
down_revision: str | None = "20260728_0116"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "commerce_payment_intents",
    "commerce_payment_events",
    "commerce_returns",
    "commerce_return_items",
    "commerce_customer_credits",
    "commerce_commissions",
)


def tenant_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
    ]


def timestamps() -> list[sa.Column]:
    return [
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
    ]


def enable_rls(table: str) -> None:
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
        "commerce_payment_intents",
        *tenant_columns(),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commerce_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_reference", sa.String(180), nullable=False),
        sa.Column("method_type", sa.String(40), nullable=False),
        sa.Column("method_last4", sa.String(4)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.CheckConstraint("amount > 0", name="ck_commerce_payment_intents_amount"),
        sa.CheckConstraint(
            "status IN ('pending', 'captured', 'failed', 'cancelled', "
            "'refund_pending', 'partially_refunded', 'refunded')",
            name="ck_commerce_payment_intents_status",
        ),
        sa.UniqueConstraint(
            "company_id",
            "idempotency_key",
            name="uq_commerce_payment_intents_company_idempotency",
        ),
        sa.UniqueConstraint(
            "company_id",
            "provider",
            "provider_reference",
            name="uq_commerce_payment_intents_provider_reference",
        ),
    )
    op.create_index(
        "ix_commerce_payment_intents_company_id",
        "commerce_payment_intents",
        ["company_id"],
    )
    op.create_index(
        "ix_commerce_payment_intents_company_order",
        "commerce_payment_intents",
        ["company_id", "order_id"],
    )
    op.create_table(
        "commerce_payment_events",
        *tenant_columns(),
        sa.Column(
            "payment_intent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commerce_payment_intents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_event_id", sa.String(180), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_commerce_payment_events_provider_event",
        ),
    )
    op.create_index(
        "ix_commerce_payment_events_company_id",
        "commerce_payment_events",
        ["company_id"],
    )
    op.create_index(
        "ix_commerce_payment_events_company_intent",
        "commerce_payment_events",
        ["company_id", "payment_intent_id"],
    )
    op.create_table(
        "commerce_returns",
        *tenant_columns(),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commerce_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stock_location_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_locations.id", ondelete="RESTRICT"),
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("resolution", sa.String(24)),
        sa.Column("refund_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "received_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('requested', 'received', 'rejected', 'cancelled')",
            name="ck_commerce_returns_status",
        ),
        sa.CheckConstraint(
            "refund_amount >= 0", name="ck_commerce_returns_refund_amount"
        ),
        sa.UniqueConstraint(
            "company_id",
            "idempotency_key",
            name="uq_commerce_returns_company_idempotency",
        ),
    )
    op.create_index(
        "ix_commerce_returns_company_id", "commerce_returns", ["company_id"]
    )
    op.create_index(
        "ix_commerce_returns_company_order",
        "commerce_returns",
        ["company_id", "order_id"],
    )
    op.create_table(
        "commerce_return_items",
        *tenant_columns(),
        sa.Column(
            "return_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commerce_returns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commerce_order_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("line_refund", sa.Numeric(16, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("quantity > 0", name="ck_commerce_return_items_quantity"),
        sa.CheckConstraint(
            "line_refund >= 0", name="ck_commerce_return_items_refund"
        ),
        sa.UniqueConstraint(
            "return_id", "order_item_id", name="uq_commerce_return_items_line"
        ),
    )
    op.create_index(
        "ix_commerce_return_items_company_id",
        "commerce_return_items",
        ["company_id"],
    )
    op.create_index(
        "ix_commerce_return_items_company_return",
        "commerce_return_items",
        ["company_id", "return_id"],
    )
    op.create_table(
        "commerce_customer_credits",
        *tenant_columns(),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commerce_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "return_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commerce_returns.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "financial_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_entries.id", ondelete="SET NULL"),
        ),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        *timestamps(),
        sa.CheckConstraint("amount > 0", name="ck_commerce_customer_credits_amount"),
        sa.CheckConstraint(
            "status IN ('issued', 'refund_pending', 'applied', 'refunded', 'void')",
            name="ck_commerce_customer_credits_status",
        ),
        sa.UniqueConstraint(
            "return_id", name="uq_commerce_customer_credits_return"
        ),
    )
    op.create_index(
        "ix_commerce_customer_credits_company_id",
        "commerce_customer_credits",
        ["company_id"],
    )
    op.create_index(
        "ix_commerce_customer_credits_company_order",
        "commerce_customer_credits",
        ["company_id", "order_id"],
    )
    op.create_table(
        "commerce_commissions",
        *tenant_columns(),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commerce_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "beneficiary_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "financial_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_entries.id", ondelete="SET NULL"),
        ),
        sa.Column("rate", sa.Numeric(7, 4), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "approved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.CheckConstraint(
            "rate > 0 AND rate <= 100", name="ck_commerce_commissions_rate"
        ),
        sa.CheckConstraint("amount > 0", name="ck_commerce_commissions_amount"),
        sa.CheckConstraint(
            "status IN ('accrued', 'approved', 'paid', 'cancelled')",
            name="ck_commerce_commissions_status",
        ),
        sa.UniqueConstraint(
            "company_id",
            "idempotency_key",
            name="uq_commerce_commissions_company_idempotency",
        ),
    )
    op.create_index(
        "ix_commerce_commissions_company_id",
        "commerce_commissions",
        ["company_id"],
    )
    op.create_index(
        "ix_commerce_commissions_company_order",
        "commerce_commissions",
        ["company_id", "order_id"],
    )
    for table in TABLES:
        enable_rls(table)
    op.execute(
        "UPDATE modules_catalog SET version = '1.2.0', updated_at = now() "
        "WHERE code = 'commerce'"
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute(
        "UPDATE modules_catalog SET version = '1.1.0', updated_at = now() "
        "WHERE code = 'commerce'"
    )
