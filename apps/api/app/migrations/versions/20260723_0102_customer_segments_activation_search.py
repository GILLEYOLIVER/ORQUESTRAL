"""Add governed customer segments, activation and search.

Revision ID: 20260723_0102
Revises: 20260723_0101
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260723_0102"
down_revision = "20260723_0101"
branch_labels = None
depends_on = None

_TENANT = "company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid"
_PERMISSIONS = (
    (
        "crm.segments.view",
        "segments.view",
        "Visualizar segmentos e busca de clientes",
    ),
    (
        "crm.segments.manage",
        "segments.manage",
        "Criar, materializar e publicar segmentos",
    ),
    (
        "crm.segments.activate",
        "segments.activate",
        "Ativar segmentos em destinos governados",
    ),
)


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
    for code, action, description in _PERMISSIONS:
        op.execute(
            sa.text(
                """
                INSERT INTO permissions (id, code, module_code, action, description)
                VALUES (
                    gen_random_uuid(), :code, 'crm', :action, :description
                )
                ON CONFLICT (code) DO NOTHING
                """
            ).bindparams(code=code, action=action, description=description)
        )
    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT role.id, permission.id
            FROM roles AS role
            CROSS JOIN permissions AS permission
            WHERE role.name::text = 'Proprietário'
              AND permission.code IN (
                  'crm.segments.view',
                  'crm.segments.manage',
                  'crm.segments.activate'
              )
            ON CONFLICT DO NOTHING
            """
        )
    )

    op.create_table(
        "customer_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "definition_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("member_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("materialized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by_user_id",
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'paused')",
            name="ck_customer_segments_status",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_customer_segments_version",
        ),
        sa.CheckConstraint(
            "member_count >= 0",
            name="ck_customer_segments_member_count",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(definition_json) = 'object'",
            name="ck_customer_segments_definition_object",
        ),
        sa.UniqueConstraint(
            "company_id",
            "name",
            name="uq_customer_segments_company_name",
        ),
    )
    op.create_index(
        "ix_customer_segments_company_status",
        "customer_segments",
        ["company_id", "status", "updated_at"],
    )

    op.create_table(
        "customer_segment_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "segment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_segments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "matched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "company_id",
            "segment_id",
            "profile_id",
            name="uq_customer_segment_members_profile",
        ),
    )
    op.create_index(
        "ix_customer_segment_members_company_segment",
        "customer_segment_members",
        ["company_id", "segment_id", "matched_at"],
    )

    op.create_table(
        "customer_segment_activations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "segment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_segments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("destination_type", sa.String(length=32), nullable=False),
        sa.Column("destination_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("eligible_count", sa.Integer(), nullable=False),
        sa.Column("activated_count", sa.Integer(), nullable=False),
        sa.Column("excluded_restricted_count", sa.Integer(), nullable=False),
        sa.Column("excluded_no_consent_count", sa.Integer(), nullable=False),
        sa.Column(
            "requested_by_user_id",
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
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "destination_type = 'marketing_campaign'",
            name="ck_customer_segment_activations_destination",
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'partial', 'blocked')",
            name="ck_customer_segment_activations_status",
        ),
        sa.CheckConstraint(
            "eligible_count >= 0 AND activated_count >= 0 "
            "AND excluded_restricted_count >= 0 "
            "AND excluded_no_consent_count >= 0",
            name="ck_customer_segment_activations_counts",
        ),
    )
    op.create_index(
        "ix_customer_segment_activations_company_segment",
        "customer_segment_activations",
        ["company_id", "segment_id", "created_at"],
    )

    op.execute(
        sa.text(
            """
            CREATE INDEX ix_customer_profiles_display_name_search
            ON customer_profiles
            USING gin (to_tsvector('simple', coalesce(display_name, '')))
            """
        )
    )

    _enable_rls("customer_segments")
    _enable_rls("customer_segment_members")
    _enable_rls("customer_segment_activations")


def downgrade() -> None:
    op.drop_index(
        "ix_customer_profiles_display_name_search",
        table_name="customer_profiles",
    )
    op.drop_table("customer_segment_activations")
    op.drop_table("customer_segment_members")
    op.drop_table("customer_segments")
    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id IN (
                SELECT id
                FROM permissions
                WHERE code IN (
                    'crm.segments.view',
                    'crm.segments.manage',
                    'crm.segments.activate'
                )
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE code IN (
                'crm.segments.view',
                'crm.segments.manage',
                'crm.segments.activate'
            )
            """
        )
    )
