"""Add versioned customer matching, reversible merges and field lineage.

Revision ID: 20260723_0092
Revises: 20260723_0091
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260723_0092"
down_revision: str | None = "20260723_0091"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME_ROLE = "orkestral_tenant_runtime"
READ_ONLY_ROLE = "orkestral_tenant_read_only"
TABLES = (
    "customer_match_rules",
    "customer_profile_merge_cases",
    "customer_profile_merge_items",
    "customer_field_lineage",
    "customer_data_governance_events",
)


def _uuid(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name,
        postgresql.UUID(as_uuid=True),
        nullable=nullable,
        server_default=sa.text("gen_random_uuid()") if name == "id" else None,
    )


def _tenant_rls(table_name: str, system_role: str) -> None:
    table = f"public.{table_name}"
    roles = f"{RUNTIME_ROLE}, {READ_ONLY_ROLE}"
    quoted_system_role = op.get_bind().dialect.identifier_preparer.quote(system_role)
    expression = "company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid"
    op.execute(sa.text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {RUNTIME_ROLE}"))
    op.execute(sa.text(f"GRANT SELECT ON {table} TO {READ_ONLY_ROLE}"))
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"CREATE POLICY orkestral_company_access ON {table} FOR ALL TO {roles} "
            f"USING ({expression}) WITH CHECK ({expression})"
        )
    )
    op.execute(
        sa.text(
            f"CREATE POLICY orkestral_system_access ON {table} FOR ALL "
            f"TO {quoted_system_role} USING (true) WITH CHECK (true)"
        )
    )
    op.execute(
        sa.text(
            f"CREATE POLICY orkestral_company_guard ON {table} AS RESTRICTIVE "
            f"FOR ALL TO {roles} USING ({expression}) WITH CHECK ({expression})"
        )
    )


def upgrade() -> None:
    op.add_column(
        "customer_profiles",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
    )
    op.add_column(
        "customer_profiles",
        sa.Column(
            "merged_into_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_profiles.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_customer_profiles_status",
        "customer_profiles",
        "status IN ('active', 'merged')",
    )
    op.create_index(
        "ix_customer_profiles_company_status",
        "customer_profiles",
        ["company_id", "status"],
    )

    op.create_table(
        "customer_match_rules",
        _uuid("id"),
        _uuid("company_id"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("threshold", sa.Float(), nullable=False, server_default="0.88"),
        sa.Column(
            "rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        _uuid("created_by_user_id"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "version", name="uq_customer_match_rule_version"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'retired')",
            name="ck_customer_match_rule_status",
        ),
        sa.CheckConstraint(
            "threshold >= 0.5 AND threshold <= 1",
            name="ck_customer_match_rule_threshold",
        ),
    )
    op.create_index(
        "ix_customer_match_rules_company_status",
        "customer_match_rules",
        ["company_id", "status"],
    )
    op.create_index(
        "uq_customer_match_rules_one_published",
        "customer_match_rules",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
    )

    op.create_table(
        "customer_profile_merge_cases",
        _uuid("id"),
        _uuid("company_id"),
        _uuid("primary_profile_id"),
        _uuid("secondary_profile_id"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column(
            "reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        _uuid("match_rule_id"),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        _uuid("requested_by_user_id"),
        _uuid("reviewed_by_user_id", nullable=True),
        _uuid("reverted_by_user_id", nullable=True),
        sa.Column("decision_note", sa.String(length=1200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["primary_profile_id"], ["customer_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["secondary_profile_id"], ["customer_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["match_rule_id"], ["customer_match_rules.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reverted_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "primary_profile_id <> secondary_profile_id",
            name="ck_customer_merge_distinct_profiles",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'reverted')",
            name="ck_customer_merge_case_status",
        ),
        sa.CheckConstraint(
            "score >= 0 AND score <= 1",
            name="ck_customer_merge_case_score",
        ),
    )
    op.create_index(
        "ix_customer_merge_cases_company_status",
        "customer_profile_merge_cases",
        ["company_id", "status", "created_at"],
    )

    op.create_table(
        "customer_profile_merge_items",
        _uuid("id"),
        _uuid("company_id"),
        _uuid("merge_case_id"),
        sa.Column("item_type", sa.String(length=80), nullable=False),
        _uuid("item_id"),
        _uuid("from_profile_id"),
        _uuid("to_profile_id"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["merge_case_id"], ["customer_profile_merge_cases.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "merge_case_id",
            "item_type",
            "item_id",
            name="uq_customer_merge_item",
        ),
    )
    op.create_index(
        "ix_customer_merge_items_company_case",
        "customer_profile_merge_items",
        ["company_id", "merge_case_id"],
    )

    op.create_table(
        "customer_field_lineage",
        _uuid("id"),
        _uuid("company_id"),
        _uuid("profile_id"),
        sa.Column("field_name", sa.String(length=80), nullable=False),
        sa.Column("value_fingerprint", sa.String(length=64), nullable=False),
        _uuid("source_id", nullable=True),
        sa.Column("source_record_id", sa.String(length=160), nullable=True),
        sa.Column(
            "classification",
            sa.String(length=20),
            nullable=False,
            server_default="internal",
        ),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.true()),
        _uuid("recorded_by_user_id"),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["customer_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["customer_data_sources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "classification IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_customer_lineage_classification",
        ),
    )
    op.create_index(
        "ix_customer_lineage_company_profile_field",
        "customer_field_lineage",
        ["company_id", "profile_id", "field_name", "observed_at"],
    )

    op.create_table(
        "customer_data_governance_events",
        _uuid("id"),
        _uuid("company_id"),
        _uuid("actor_user_id"),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("subject_type", sa.String(length=80), nullable=False),
        _uuid("subject_id"),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_customer_governance_events_company_created",
        "customer_data_governance_events",
        ["company_id", "created_at"],
    )

    system_role = str(op.get_bind().scalar(sa.text("SELECT current_user")))
    for table_name in TABLES:
        _tenant_rls(table_name, system_role)


def downgrade() -> None:
    op.drop_table("customer_data_governance_events")
    op.drop_table("customer_field_lineage")
    op.drop_table("customer_profile_merge_items")
    op.drop_table("customer_profile_merge_cases")
    op.drop_table("customer_match_rules")
    op.drop_index("ix_customer_profiles_company_status", table_name="customer_profiles")
    op.drop_constraint(
        "ck_customer_profiles_status",
        "customer_profiles",
        type_="check",
    )
    op.drop_column("customer_profiles", "merged_into_profile_id")
    op.drop_column("customer_profiles", "status")
