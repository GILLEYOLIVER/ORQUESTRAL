"""commerce variants promotions and deterministic pricing

Revision ID: 20260727_0115
Revises: 20260727_0114
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260727_0115"
down_revision: str | None = "20260727_0114"
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
    op.execute("""
        INSERT INTO modules_catalog (code,name,description,version,category,is_core,status)
        VALUES ('commerce','Comércio e receita','Catálogo, preços, promoções e pedidos.','1.0.0','Comercial',false,'installed')
        ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name,description=EXCLUDED.description,
          version=EXCLUDED.version,category=EXCLUDED.category,status='installed',updated_at=now()
    """)
    permissions = (
        ("commerce.view", "view", "Visualizar comércio e receita"),
        ("commerce.catalog.manage", "catalog.manage", "Gerenciar variantes comerciais"),
        ("commerce.promotions.manage", "promotions.manage", "Gerenciar promoções"),
        ("commerce.pricing.resolve", "pricing.resolve", "Calcular preços e descontos"),
    )
    for code, action, description in permissions:
        op.execute(
            sa.text("""
                INSERT INTO permissions (id,code,module_code,action,description)
                VALUES (gen_random_uuid(),:code,'commerce',:action,:description)
                ON CONFLICT (code) DO UPDATE SET module_code='commerce',
                  action=EXCLUDED.action,description=EXCLUDED.description
            """).bindparams(code=code, action=action, description=description)
        )
    op.execute("""
        INSERT INTO role_permissions (role_id,permission_id)
        SELECT r.id,p.id FROM roles r CROSS JOIN permissions p
        WHERE r.is_system_role=true AND r.name IN ('Proprietário','Proprietario')
          AND p.module_code='commerce' ON CONFLICT DO NOTHING
    """)
    op.create_table(
        "commerce_product_variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku", sa.String(100), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("attributes", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "sku", name="uq_commerce_variants_company_sku"),
    )
    op.create_table(
        "commerce_promotions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("code", sa.String(80), nullable=True),
        sa.Column("discount_type", sa.String(16), nullable=False),
        sa.Column("discount_value", sa.Numeric(16, 2), nullable=False),
        sa.Column("applies_to", sa.String(16), nullable=False),
        sa.Column("minimum_quantity", sa.Numeric(14, 3), server_default="1", nullable=False),
        sa.Column("max_redemptions", sa.Integer(), nullable=True),
        sa.Column("redeemed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), server_default="draft", nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("discount_type IN ('percent','fixed')", name="ck_commerce_promotions_discount_type"),
        sa.CheckConstraint("status IN ('draft','active','paused','expired')", name="ck_commerce_promotions_status"),
        sa.CheckConstraint("applies_to IN ('all','item','variant')", name="ck_commerce_promotions_applies_to"),
        sa.CheckConstraint("discount_value >= 0", name="ck_commerce_promotions_value"),
        sa.CheckConstraint("discount_type <> 'percent' OR discount_value <= 100", name="ck_commerce_promotions_percent"),
        sa.CheckConstraint("minimum_quantity > 0", name="ck_commerce_promotions_minimum"),
        sa.CheckConstraint("max_redemptions IS NULL OR max_redemptions > 0", name="ck_commerce_promotions_max_redemptions"),
        sa.CheckConstraint("redeemed_count >= 0", name="ck_commerce_promotions_redeemed"),
        sa.CheckConstraint("(applies_to='all' AND inventory_item_id IS NULL AND variant_id IS NULL) OR (applies_to='item' AND inventory_item_id IS NOT NULL AND variant_id IS NULL) OR (applies_to='variant' AND variant_id IS NOT NULL)", name="ck_commerce_promotions_target"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["commerce_product_variants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "code", name="uq_commerce_promotions_company_code"),
    )
    indexes = {
        "commerce_product_variants": ("company_id","inventory_item_id","sku","name","active","created_by_user_id"),
        "commerce_promotions": ("company_id","inventory_item_id","variant_id","name","code","starts_at","ends_at","status","created_by_user_id"),
    }
    for table, columns in indexes.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])
        _rls(table)
    op.create_index("ix_commerce_variants_company_item", "commerce_product_variants", ["company_id","inventory_item_id"])
    op.create_index("ix_commerce_promotions_company_status", "commerce_promotions", ["company_id","status"])


def downgrade() -> None:
    for table in ("commerce_promotions", "commerce_product_variants"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.drop_table(table)
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE module_code='commerce')")
    op.execute("DELETE FROM permissions WHERE module_code='commerce'")
    op.execute("DELETE FROM modules_catalog WHERE code='commerce'")
