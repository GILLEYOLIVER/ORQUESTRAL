"""commerce orders reservations contracts and customer subscriptions

Revision ID: 20260728_0116
Revises: 20260727_0115
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260728_0116"
down_revision: str | None = "20260727_0115"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f"""CREATE POLICY {table}_tenant_isolation ON "{table}"
        USING (company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid)
        WITH CHECK (company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid)"""
    )


def upgrade() -> None:
    permissions = (
        ("commerce.orders.manage", "orders.manage", "Criar e reservar pedidos"),
        (
            "commerce.orders.confirm",
            "orders.confirm",
            "Confirmar pedidos e gerar efeitos financeiros",
        ),
        ("commerce.contracts.view", "contracts.view", "Visualizar contratos comerciais"),
    )
    for code, action, description in permissions:
        op.execute(
            sa.text(
                """
                INSERT INTO permissions (id,code,module_code,action,description)
                VALUES (gen_random_uuid(),:code,'commerce',:action,:description)
                ON CONFLICT (code) DO UPDATE SET module_code='commerce',
                  action=EXCLUDED.action,description=EXCLUDED.description
                """
            ).bindparams(code=code, action=action, description=description)
        )
    op.execute(
        """
        INSERT INTO role_permissions (role_id,permission_id)
        SELECT role.id,permission.id FROM roles AS role
        CROSS JOIN permissions AS permission
        WHERE role.is_system_role=true
          AND role.name IN ('Proprietário','Proprietario')
          AND permission.code IN (
            'commerce.orders.manage','commerce.orders.confirm','commerce.contracts.view'
          )
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        "UPDATE modules_catalog SET version='1.1.0',updated_at=now() WHERE code='commerce'"
    )
    op.create_table(
        "commerce_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("financial_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("order_number", sa.String(60), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("subtotal", sa.Numeric(16, 2), nullable=False),
        sa.Column("discount_total", sa.Numeric(16, 2), nullable=False),
        sa.Column("total", sa.Numeric(16, 2), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft','reserved','confirmed','fulfilled','cancelled')", name="ck_commerce_orders_status"),
        sa.CheckConstraint("subtotal >= 0 AND discount_total >= 0 AND total >= 0", name="ck_commerce_orders_totals"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["quote_id"], ["crm_quotes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["account_id"], ["crm_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["financial_entry_id"], ["financial_entries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("financial_entry_id"),
        sa.UniqueConstraint("quote_id", name="uq_commerce_orders_quote"),
        sa.UniqueConstraint("company_id", "order_number", name="uq_commerce_orders_number"),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_commerce_orders_idempotency"),
    )
    op.create_table(
        "commerce_order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sku_snapshot", sa.String(100), nullable=False),
        sa.Column("description_snapshot", sa.String(300), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(16, 2), nullable=False),
        sa.Column("discount_total", sa.Numeric(16, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(16, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_commerce_order_items_quantity"),
        sa.CheckConstraint("unit_price >= 0 AND discount_total >= 0 AND line_total >= 0", name="ck_commerce_order_items_totals"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["commerce_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["variant_id"], ["commerce_product_variants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "commerce_inventory_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("status", sa.String(16), server_default="reserved", nullable=False),
        sa.Column("reserved_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reserved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('reserved','consumed','released')", name="ck_commerce_reservations_status"),
        sa.CheckConstraint("quantity > 0", name="ck_commerce_reservations_quantity"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["commerce_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_item_id"], ["commerce_order_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reserved_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_item_id", name="uq_commerce_reservations_order_item"),
    )
    op.create_table(
        "commerce_contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("contract_number", sa.String(60), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("total_value", sa.Numeric(16, 2), nullable=False),
        sa.Column("terms", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft','active','suspended','completed','cancelled')", name="ck_commerce_contracts_status"),
        sa.CheckConstraint("total_value >= 0", name="ck_commerce_contracts_total"),
        sa.CheckConstraint("ends_on IS NULL OR ends_on >= starts_on", name="ck_commerce_contracts_period"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["commerce_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["account_id"], ["crm_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "contract_number", name="uq_commerce_contracts_number"),
        sa.UniqueConstraint("order_id", name="uq_commerce_contracts_order"),
    )
    op.create_table(
        "commerce_customer_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("billing_interval", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("current_period_start", sa.Date(), nullable=False),
        sa.Column("current_period_end", sa.Date(), nullable=False),
        sa.Column("next_billing_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active','paused','past_due','cancelled','completed')", name="ck_commerce_customer_subscriptions_status"),
        sa.CheckConstraint("billing_interval IN ('monthly','yearly')", name="ck_commerce_customer_subscriptions_interval"),
        sa.CheckConstraint("amount >= 0", name="ck_commerce_customer_subscriptions_amount"),
        sa.CheckConstraint("current_period_end > current_period_start", name="ck_commerce_customer_subscriptions_period"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contract_id"], ["commerce_contracts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["crm_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contract_id", name="uq_commerce_customer_subscriptions_contract"),
    )
    indexes = {
        "commerce_orders": ("company_id","quote_id","account_id","financial_entry_id","order_number","status","created_by_user_id"),
        "commerce_order_items": ("company_id","order_id","inventory_item_id","variant_id"),
        "commerce_inventory_reservations": ("company_id","order_id","order_item_id","inventory_item_id","location_id","status","reserved_by_user_id"),
        "commerce_contracts": ("company_id","order_id","account_id","contract_number","status","created_by_user_id"),
        "commerce_customer_subscriptions": ("company_id","contract_id","account_id","status","next_billing_on"),
    }
    for table, columns in indexes.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])
        _rls(table)
    op.create_index("ix_commerce_orders_company_status", "commerce_orders", ["company_id","status"])
    op.create_index("ix_commerce_reservations_availability", "commerce_inventory_reservations", ["company_id","inventory_item_id","location_id","status"])
    op.create_index("ix_commerce_customer_subscriptions_company_status", "commerce_customer_subscriptions", ["company_id","status"])


def downgrade() -> None:
    for table in (
        "commerce_customer_subscriptions",
        "commerce_contracts",
        "commerce_inventory_reservations",
        "commerce_order_items",
        "commerce_orders",
    ):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.drop_table(table)
    op.execute(
        """
        DELETE FROM role_permissions WHERE permission_id IN (
          SELECT id FROM permissions WHERE code IN (
            'commerce.orders.manage','commerce.orders.confirm','commerce.contracts.view'
          )
        )
        """
    )
    op.execute(
        "DELETE FROM permissions WHERE code IN ('commerce.orders.manage','commerce.orders.confirm','commerce.contracts.view')"
    )
    op.execute(
        "UPDATE modules_catalog SET version='1.0.0',updated_at=now() WHERE code='commerce'"
    )
