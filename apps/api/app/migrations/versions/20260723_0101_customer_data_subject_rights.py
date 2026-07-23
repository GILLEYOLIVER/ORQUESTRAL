"""Add governed customer data-subject rights.

Revision ID: 20260723_0101
Revises: 20260723_0100
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260723_0101"
down_revision = "20260723_0100"
branch_labels = None
depends_on = None

_TENANT = "company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid"


def _enable_rls(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING ({_TENANT})
            WITH CHECK ({_TENANT})
            """
        )
    )


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO permissions (id, code, module_code, action, description)
            VALUES (
                gen_random_uuid(),
                'crm.contacts.export',
                'crm',
                'contacts.export',
                'Exportar dados pessoais governados do CRM'
            )
            ON CONFLICT (code) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT role.id, permission.id
            FROM roles AS role
            CROSS JOIN permissions AS permission
            WHERE role.name::text = 'Proprietário'
              AND permission.code = 'crm.contacts.export'
            ON CONFLICT DO NOTHING
            """
        )
    )
    op.create_table(
        "customer_processing_restrictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column(
            "requested_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "enforced_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "released_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "enforced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'released')",
            name="ck_customer_processing_restrictions_status",
        ),
        sa.CheckConstraint(
            "reason_code IN "
            "('accuracy_dispute', 'legal_request', 'consent_withdrawn', "
            "'fraud_review', 'other_governed_reason')",
            name="ck_customer_processing_restrictions_reason",
        ),
        sa.UniqueConstraint(
            "company_id",
            "profile_id",
            name="uq_customer_processing_restrictions_profile",
        ),
    )
    op.create_index(
        "ix_customer_processing_restrictions_company_status",
        "customer_processing_restrictions",
        ["company_id", "status", "enforced_at"],
    )

    op.create_table(
        "customer_privacy_right_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("operation_type", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column(
            "field_names",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "performed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "operation_type IN "
            "('access_export', 'correction', 'restriction', 'restriction_release')",
            name="ck_customer_privacy_right_operations_type",
        ),
        sa.CheckConstraint(
            "outcome IN ('completed', 'blocked', 'failed')",
            name="ck_customer_privacy_right_operations_outcome",
        ),
    )
    op.create_index(
        "ix_customer_privacy_right_operations_company_created",
        "customer_privacy_right_operations",
        ["company_id", "created_at"],
    )

    _enable_rls("customer_processing_restrictions")
    _enable_rls("customer_privacy_right_operations")


def downgrade() -> None:
    op.drop_table("customer_privacy_right_operations")
    op.drop_table("customer_processing_restrictions")
    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id = (
                SELECT id FROM permissions WHERE code = 'crm.contacts.export'
            )
            """
        )
    )
    op.execute(
        sa.text("DELETE FROM permissions WHERE code = 'crm.contacts.export'")
    )
