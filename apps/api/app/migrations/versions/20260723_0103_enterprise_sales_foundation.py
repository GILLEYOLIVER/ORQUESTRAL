"""enterprise sales accounts leads and governed conversion

Revision ID: 20260723_0103
Revises: 20260723_0102
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0103"
down_revision: str | None = "20260723_0102"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = (
    ("crm.accounts.view", "accounts.view", "Visualizar contas empresariais"),
    ("crm.accounts.manage", "accounts.manage", "Gerenciar contas empresariais"),
    ("crm.leads.view", "leads.view", "Visualizar leads comerciais"),
    ("crm.leads.manage", "leads.manage", "Gerenciar leads comerciais"),
    ("crm.leads.qualify", "leads.qualify", "Qualificar leads comerciais"),
    ("crm.leads.convert", "leads.convert", "Converter leads qualificados"),
)


def _tenant_policy(table: str) -> None:
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
        "crm_accounts",
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
        sa.Column("name", postgresql.CITEXT(), nullable=False),
        sa.Column("legal_name", sa.String(length=200), nullable=True),
        sa.Column("website", sa.String(length=240), nullable=True),
        sa.Column("industry", sa.String(length=120), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("annual_revenue", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="BRL", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="prospect", nullable=False),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('prospect', 'customer', 'partner', 'inactive')",
            name="ck_crm_accounts_status",
        ),
        sa.CheckConstraint(
            "annual_revenue >= 0", name="ck_crm_accounts_annual_revenue"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_crm_accounts_company_name"),
    )
    op.create_index("ix_crm_accounts_company_id", "crm_accounts", ["company_id"])
    op.create_index("ix_crm_accounts_name", "crm_accounts", ["name"])
    op.create_index("ix_crm_accounts_industry", "crm_accounts", ["industry"])
    op.create_index("ix_crm_accounts_owner_user_id", "crm_accounts", ["owner_user_id"])
    op.create_index("ix_crm_accounts_status", "crm_accounts", ["status"])
    op.create_index("ix_crm_accounts_created_at", "crm_accounts", ["created_at"])
    op.create_index("ix_crm_accounts_deleted_at", "crm_accounts", ["deleted_at"])

    op.add_column(
        "crm_contacts",
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_crm_contacts_account_id", "crm_contacts", ["account_id"])
    op.add_column(
        "crm_opportunities",
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_crm_opportunities_account_id", "crm_opportunities", ["account_id"])

    op.create_table(
        "crm_leads",
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
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("company_name", sa.String(length=180), nullable=True),
        sa.Column("job_title", sa.String(length=120), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="new", nullable=False),
        sa.Column("score", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("qualification_note", sa.Text(), nullable=True),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "converted_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "converted_contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "converted_opportunity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_opportunities.id", ondelete="SET NULL"),
            nullable=True,
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('new', 'working', 'qualified', 'converted', 'disqualified')",
            name="ck_crm_leads_status",
        ),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_crm_leads_score"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "name",
        "email",
        "company_name",
        "source",
        "status",
        "score",
        "owner_user_id",
        "qualified_at",
        "converted_at",
        "converted_account_id",
        "converted_contact_id",
        "converted_opportunity_id",
        "created_at",
        "deleted_at",
    ):
        op.create_index(f"ix_crm_leads_{column}", "crm_leads", [column])

    _tenant_policy("crm_accounts")
    _tenant_policy("crm_leads")

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
            'crm.accounts.view',
            'crm.accounts.manage',
            'crm.leads.view',
            'crm.leads.manage',
            'crm.leads.qualify',
            'crm.leads.convert'
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
              'crm.accounts.view',
              'crm.accounts.manage',
              'crm.leads.view',
              'crm.leads.manage',
              'crm.leads.qualify',
              'crm.leads.convert'
            )
        )
        """
    )
    op.execute(
        """
        DELETE FROM permissions
        WHERE code IN (
          'crm.accounts.view',
          'crm.accounts.manage',
          'crm.leads.view',
          'crm.leads.manage',
          'crm.leads.qualify',
          'crm.leads.convert'
        )
        """
    )
    op.drop_table("crm_leads")
    op.drop_index("ix_crm_opportunities_account_id", table_name="crm_opportunities")
    op.drop_column("crm_opportunities", "account_id")
    op.drop_index("ix_crm_contacts_account_id", table_name="crm_contacts")
    op.drop_column("crm_contacts", "account_id")
    op.drop_table("crm_accounts")
