"""Instala contas, categorias e lancamentos financeiros.

Revision ID: 20260720_0020
Revises: 20260720_0019
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0020"
down_revision: str | None = "20260720_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = (
    ("finance.view", "finance", "view", "Visualizar financeiro"),
    ("finance.accounts.manage", "finance", "accounts.manage", "Gerenciar contas financeiras"),
    ("finance.entries.create", "finance", "entries.create", "Criar lancamentos"),
    ("finance.entries.update", "finance", "entries.update", "Atualizar lancamentos"),
    ("finance.entries.settle", "finance", "entries.settle", "Baixar lancamentos"),
    ("finance.categories.manage", "finance", "categories.manage", "Gerenciar categorias"),
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
        VALUES ('finance', 'Financeiro', 'Gestao financeira empresarial.', '1.0.0', 'Gestao', false, 'installed')
        ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description,
            version = EXCLUDED.version, category = EXCLUDED.category, status = 'installed', updated_at = now()
    """)
    )
    op.execute(
        sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT roles.id, permissions.id FROM roles JOIN permissions ON permissions.module_code = 'finance'
        WHERE roles.is_system_role = true AND roles.name IN ('Proprietário', 'Proprietario') ON CONFLICT DO NOTHING
    """)
    )
    op.create_table(
        "financial_accounts",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("account_type", sa.String(length=30), nullable=False),
        sa.Column("opening_balance", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "account_type IN ('bank', 'cash', 'payment_gateway')", name="ck_financial_accounts_type"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_financial_accounts_company_name"),
    )
    for column in ("company_id", "name", "account_type", "active"):
        op.create_index(f"ix_financial_accounts_{column}", "financial_accounts", [column])
    op.create_table(
        "financial_categories",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("entry_type", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "entry_type IN ('income', 'expense')", name="ck_financial_categories_entry_type"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "entry_type", "name", name="uq_financial_categories_scope"
        ),
    )
    for column in ("company_id", "name", "entry_type", "active"):
        op.create_index(f"ix_financial_categories_{column}", "financial_categories", [column])
    op.create_table(
        "financial_entries",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("entry_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("competence_date", sa.Date(), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_method", sa.String(length=60), nullable=True),
        sa.Column("reference", sa.String(length=120), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("entry_type IN ('income', 'expense')", name="ck_financial_entries_type"),
        sa.CheckConstraint(
            "status IN ('pending', 'settled', 'cancelled')", name="ck_financial_entries_status"
        ),
        sa.CheckConstraint("amount > 0", name="ck_financial_entries_amount"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["financial_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["category_id"], ["financial_categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "account_id",
        "category_id",
        "created_by_user_id",
        "description",
        "entry_type",
        "status",
        "due_date",
        "competence_date",
        "settled_at",
        "reference",
        "created_at",
    ):
        op.create_index(f"ix_financial_entries_{column}", "financial_entries", [column])
    op.create_index(
        "ix_financial_entries_company_due", "financial_entries", ["company_id", "due_date"]
    )
    op.create_index(
        "ix_financial_entries_company_status", "financial_entries", ["company_id", "status"]
    )


def downgrade() -> None:
    op.drop_table("financial_entries")
    op.drop_table("financial_categories")
    op.drop_table("financial_accounts")
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE module_code = 'finance')"
        )
    )
    op.execute(sa.text("DELETE FROM permissions WHERE module_code = 'finance'"))
    op.execute(
        sa.text(
            "UPDATE modules_catalog SET status = 'planned', updated_at = now() WHERE code = 'finance'"
        )
    )
