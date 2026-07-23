"""sales price books and governed quotes

Revision ID: 20260723_0104
Revises: 20260723_0103
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0104"
down_revision: str | None = "20260723_0103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = (
    ("crm.catalog.view", "catalog.view", "Visualizar catálogo e tabelas de preços"),
    ("crm.catalog.manage", "catalog.manage", "Gerenciar tabelas de preços"),
    ("crm.quotes.view", "quotes.view", "Visualizar propostas comerciais"),
    ("crm.quotes.manage", "quotes.manage", "Criar e editar propostas comerciais"),
    ("crm.quotes.publish", "quotes.publish", "Publicar e decidir propostas comerciais"),
)


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
        "crm_price_books",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("currency", sa.String(3), server_default="BRL", nullable=False),
        sa.Column("status", sa.String(16), server_default="draft", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "published_at", sa.DateTime(timezone=True), nullable=True
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
            "status IN ('draft', 'published', 'archived')",
            name="ck_crm_price_books_status",
        ),
        sa.CheckConstraint("version > 0", name="ck_crm_price_books_version"),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from",
            name="ck_crm_price_books_validity",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "name", "version", name="uq_crm_price_books_version"
        ),
    )
    op.create_index("ix_crm_price_books_company_id", "crm_price_books", ["company_id"])
    op.create_index("ix_crm_price_books_status", "crm_price_books", ["status"])

    op.create_table(
        "crm_price_book_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "price_book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_price_books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inventory_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("unit_price", sa.Numeric(16, 2), nullable=False),
        sa.Column("minimum_quantity", sa.Numeric(14, 3), server_default="1", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
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
        sa.CheckConstraint("unit_price >= 0", name="ck_crm_price_entries_price"),
        sa.CheckConstraint(
            "minimum_quantity > 0", name="ck_crm_price_entries_minimum"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "price_book_id",
            "inventory_item_id",
            name="uq_crm_price_book_inventory_item",
        ),
    )
    op.create_index(
        "ix_crm_price_book_entries_company_id",
        "crm_price_book_entries",
        ["company_id"],
    )
    op.create_index(
        "ix_crm_price_book_entries_price_book_id",
        "crm_price_book_entries",
        ["price_book_id"],
    )

    op.create_table(
        "crm_quotes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opportunity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_opportunities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "price_book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_price_books.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quote_number", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(16), server_default="draft", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("subtotal", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("discount_total", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("total", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('draft', 'published', 'accepted', 'rejected', 'expired')",
            name="ck_crm_quotes_status",
        ),
        sa.CheckConstraint(
            "subtotal >= 0 AND discount_total >= 0 AND total >= 0",
            name="ck_crm_quotes_totals",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "quote_number", name="uq_crm_quotes_number"
        ),
    )
    op.create_index("ix_crm_quotes_company_id", "crm_quotes", ["company_id"])
    op.create_index("ix_crm_quotes_opportunity_id", "crm_quotes", ["opportunity_id"])
    op.create_index("ix_crm_quotes_status", "crm_quotes", ["status"])

    op.create_table(
        "crm_quote_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "quote_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_quotes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inventory_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sku_snapshot", sa.String(80), nullable=False),
        sa.Column("description_snapshot", sa.String(300), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(16, 2), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), server_default="0", nullable=False),
        sa.Column("line_total", sa.Numeric(16, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="ck_crm_quote_items_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_crm_quote_items_price"),
        sa.CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100",
            name="ck_crm_quote_items_discount",
        ),
        sa.CheckConstraint("line_total >= 0", name="ck_crm_quote_items_total"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_quote_items_company_id", "crm_quote_items", ["company_id"])
    op.create_index("ix_crm_quote_items_quote_id", "crm_quote_items", ["quote_id"])

    for table in (
        "crm_price_books",
        "crm_price_book_entries",
        "crm_quotes",
        "crm_quote_items",
    ):
        _rls(table)

    for code, action, description in PERMISSIONS:
        op.execute(
            sa.text(
                """
                INSERT INTO permissions (id, code, module_code, action, description)
                VALUES (gen_random_uuid(), :code, 'crm', :action, :description)
                ON CONFLICT (code) DO UPDATE
                SET module_code = EXCLUDED.module_code,
                    action = EXCLUDED.action,
                    description = EXCLUDED.description
                """
            ).bindparams(code=code, action=action, description=description)
        )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT role.id, permission.id
        FROM roles AS role
        CROSS JOIN permissions AS permission
        WHERE role.name = 'Proprietário'
          AND permission.code IN (
            'crm.catalog.view', 'crm.catalog.manage', 'crm.quotes.view',
            'crm.quotes.manage', 'crm.quotes.publish'
          )
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
          SELECT id FROM permissions
          WHERE code IN (
            'crm.catalog.view', 'crm.catalog.manage', 'crm.quotes.view',
            'crm.quotes.manage', 'crm.quotes.publish'
          )
        )
        """
    )
    op.execute(
        """
        DELETE FROM permissions
        WHERE code IN (
          'crm.catalog.view', 'crm.catalog.manage', 'crm.quotes.view',
          'crm.quotes.manage', 'crm.quotes.publish'
        )
        """
    )
    op.drop_table("crm_quote_items")
    op.drop_table("crm_quotes")
    op.drop_table("crm_price_book_entries")
    op.drop_table("crm_price_books")
