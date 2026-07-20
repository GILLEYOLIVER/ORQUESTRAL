"""Instala itens, locais, saldos e movimentacoes de estoque.

Revision ID: 20260720_0019
Revises: 20260720_0018
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0019"
down_revision: str | None = "20260720_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = (
    ("inventory.view", "inventory", "view", "Visualizar estoque"),
    ("inventory.items.manage", "inventory", "items.manage", "Gerenciar itens"),
    ("inventory.movements.create", "inventory", "movements.create", "Registrar movimentacoes"),
    ("inventory.locations.manage", "inventory", "locations.manage", "Gerenciar locais"),
    ("inventory.categories.manage", "inventory", "categories.manage", "Gerenciar categorias"),
)


def _id() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def upgrade() -> None:
    permission_table = sa.table(
        "permissions",
        sa.column("code", sa.String()),
        sa.column("module_code", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        permission_table,
        [
            {"code": code, "module_code": module, "action": action, "description": description}
            for code, module, action, description in PERMISSIONS
        ],
    )
    op.execute(
        sa.text("""
        INSERT INTO modules_catalog (code, name, description, version, category, is_core, status)
        VALUES ('inventory', 'Estoque', 'Controle de itens e movimentacoes.', '1.0.0', 'Operacoes', false, 'installed')
        ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description,
            version = EXCLUDED.version, category = EXCLUDED.category, status = 'installed', updated_at = now()
    """)
    )
    op.execute(
        sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT roles.id, permissions.id FROM roles JOIN permissions ON permissions.module_code = 'inventory'
        WHERE roles.is_system_role = true AND roles.name IN ('Proprietário', 'Proprietario') ON CONFLICT DO NOTHING
    """)
    )
    op.create_table(
        "inventory_categories",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_inventory_categories_company_name"),
    )
    for column in ("company_id", "name", "active"):
        op.create_index(f"ix_inventory_categories_{column}", "inventory_categories", [column])
    op.create_table(
        "inventory_locations",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "code", name="uq_inventory_locations_company_code"),
    )
    for column in ("company_id", "code", "name", "active"):
        op.create_index(f"ix_inventory_locations_{column}", "inventory_locations", [column])
    op.create_table(
        "inventory_items",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=20), server_default="unit", nullable=False),
        sa.Column("minimum_stock", sa.Numeric(14, 3), server_default="0", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "unit IN ('unit', 'kg', 'g', 'l', 'ml', 'm', 'box')", name="ck_inventory_items_unit"
        ),
        sa.CheckConstraint("minimum_stock >= 0", name="ck_inventory_items_minimum_stock"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["inventory_categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "sku", name="uq_inventory_items_company_sku"),
    )
    for column in (
        "company_id",
        "category_id",
        "created_by_user_id",
        "sku",
        "name",
        "active",
        "archived_at",
        "created_at",
    ):
        op.create_index(f"ix_inventory_items_{column}", "inventory_items", [column])
    op.create_index(
        "ix_inventory_items_company_active", "inventory_items", ["company_id", "active"]
    )
    op.create_table(
        "inventory_balances",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), server_default="0", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("quantity >= 0", name="ck_inventory_balances_quantity"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id", "location_id", name="uq_inventory_balances_item_location"),
    )
    for column in ("company_id", "item_id", "location_id"):
        op.create_index(f"ix_inventory_balances_{column}", "inventory_balances", [column])
    op.create_index(
        "ix_inventory_balances_company_item", "inventory_balances", ["company_id", "item_id"]
    )
    op.create_table(
        "inventory_movements",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("movement_type", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("previous_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("resulting_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("reference", sa.String(length=120), nullable=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "movement_type IN ('in', 'out', 'adjustment')", name="ck_inventory_movements_type"
        ),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_movements_quantity"),
        sa.CheckConstraint(
            "previous_quantity >= 0 AND resulting_quantity >= 0",
            name="ck_inventory_movements_balances",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "item_id",
        "location_id",
        "created_by_user_id",
        "movement_type",
        "reference",
        "occurred_at",
    ):
        op.create_index(f"ix_inventory_movements_{column}", "inventory_movements", [column])
    op.create_index(
        "ix_inventory_movements_company_occurred",
        "inventory_movements",
        ["company_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_table("inventory_movements")
    op.drop_table("inventory_balances")
    op.drop_table("inventory_items")
    op.drop_table("inventory_locations")
    op.drop_table("inventory_categories")
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE module_code = 'inventory')"
        )
    )
    op.execute(sa.text("DELETE FROM permissions WHERE module_code = 'inventory'"))
    op.execute(
        sa.text(
            "UPDATE modules_catalog SET status = 'planned', updated_at = now() WHERE code = 'inventory'"
        )
    )
