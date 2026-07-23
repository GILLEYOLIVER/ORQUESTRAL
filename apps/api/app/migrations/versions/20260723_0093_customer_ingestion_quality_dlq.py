"""Add governed customer ingestion, quality rules and dead-letter handling.

Revision ID: 20260723_0093
Revises: 20260723_0092
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260723_0093"
down_revision: str | None = "20260723_0092"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME_ROLE = "orkestral_tenant_runtime"
READ_ONLY_ROLE = "orkestral_tenant_read_only"
TABLES = (
    "customer_quality_rule_sets",
    "customer_ingestion_jobs",
    "customer_ingestion_records",
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
    op.create_table(
        "customer_quality_rule_sets",
        _uuid("id"),
        _uuid("company_id"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
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
        sa.UniqueConstraint(
            "company_id",
            "version",
            name="uq_customer_quality_rule_set_version",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'retired')",
            name="ck_customer_quality_rule_set_status",
        ),
    )
    op.create_index(
        "uq_customer_quality_rule_sets_one_published",
        "customer_quality_rule_sets",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
    )

    op.create_table(
        "customer_ingestion_jobs",
        _uuid("id"),
        _uuid("company_id"),
        _uuid("source_id"),
        _uuid("quality_rule_set_id"),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("cursor", sa.String(length=500), nullable=True),
        sa.Column("total_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_records", sa.Integer(), nullable=False, server_default="0"),
        _uuid("requested_by_user_id"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["customer_data_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["quality_rule_set_id"], ["customer_quality_rule_sets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "idempotency_key",
            name="uq_customer_ingestion_idempotency",
        ),
        sa.CheckConstraint(
            "mode IN ('batch', 'incremental')",
            name="ck_customer_ingestion_job_mode",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'partial', 'failed')",
            name="ck_customer_ingestion_job_status",
        ),
    )
    op.create_index(
        "ix_customer_ingestion_jobs_company_created",
        "customer_ingestion_jobs",
        ["company_id", "created_at"],
    )

    op.create_table(
        "customer_ingestion_records",
        _uuid("id"),
        _uuid("company_id"),
        _uuid("job_id"),
        sa.Column("source_record_id", sa.String(length=160), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column(
            "errors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        _uuid("profile_id", nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["customer_ingestion_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["customer_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id",
            "source_record_id",
            name="uq_customer_ingestion_job_source_record",
        ),
        sa.CheckConstraint(
            "status IN ('accepted', 'rejected', 'dead_letter')",
            name="ck_customer_ingestion_record_status",
        ),
    )
    op.create_index(
        "ix_customer_ingestion_records_company_status",
        "customer_ingestion_records",
        ["company_id", "status", "created_at"],
    )

    system_role = str(op.get_bind().scalar(sa.text("SELECT current_user")))
    for table_name in TABLES:
        _tenant_rls(table_name, system_role)


def downgrade() -> None:
    op.drop_table("customer_ingestion_records")
    op.drop_table("customer_ingestion_jobs")
    op.drop_table("customer_quality_rule_sets")
