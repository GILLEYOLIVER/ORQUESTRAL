"""Add canonical customer identity, sources, quality and consent.

Revision ID: 20260723_0091
Revises: 20260723_0090
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260723_0091"
down_revision: str | None = "20260723_0090"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME_ROLE = "orkestral_tenant_runtime"
READ_ONLY_ROLE = "orkestral_tenant_read_only"
TABLES = (
    "customer_data_sources",
    "customer_profiles",
    "customer_profile_contacts",
    "customer_identities",
    "customer_consents",
)


def _uuid(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


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
        "customer_data_sources",
        _uuid("id"),
        _uuid("company_id"),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("mode", sa.String(24), server_default="system_of_record", nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "mode IN ('system_of_record', 'copied', 'federated', 'cached')",
            name="ck_customer_data_source_mode",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'retired')",
            name="ck_customer_data_source_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "code", name="uq_customer_data_source_code"),
    )
    op.create_table(
        "customer_profiles",
        _uuid("id"),
        _uuid("company_id"),
        _uuid("master_contact_id", nullable=True),
        sa.Column("display_name", sa.String(180), nullable=False),
        sa.Column("profile_type", sa.String(20), server_default="person", nullable=False),
        sa.Column("lifecycle_status", sa.String(20), server_default="lead", nullable=False),
        sa.Column("quality_score", sa.Integer(), server_default="0", nullable=False),
        _uuid("created_by_user_id", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "profile_type IN ('person', 'organization')",
            name="ck_customer_profile_type",
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('lead', 'prospect', 'customer', 'inactive')",
            name="ck_customer_profile_lifecycle",
        ),
        sa.CheckConstraint(
            "quality_score BETWEEN 0 AND 100",
            name="ck_customer_profile_quality",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["master_contact_id"], ["crm_contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "customer_profile_contacts",
        _uuid("company_id"),
        _uuid("profile_id"),
        _uuid("contact_id"),
        sa.Column("link_role", sa.String(24), nullable=False),
        sa.Column("match_confidence", sa.Integer(), server_default="100", nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "link_role IN ('master', 'matched', 'duplicate_candidate')",
            name="ck_customer_profile_contact_role",
        ),
        sa.CheckConstraint(
            "match_confidence BETWEEN 0 AND 100",
            name="ck_customer_profile_contact_confidence",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["customer_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["crm_contacts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("profile_id", "contact_id"),
    )
    op.create_table(
        "customer_identities",
        _uuid("id"),
        _uuid("company_id"),
        _uuid("profile_id"),
        _uuid("data_source_id"),
        sa.Column("identity_type", sa.String(24), nullable=False),
        sa.Column("value_hash", sa.String(64), nullable=False),
        sa.Column("display_hint", sa.String(100), nullable=False),
        sa.Column("verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "identity_type IN ('email', 'phone', 'external_id', 'document')",
            name="ck_customer_identity_type",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["customer_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["data_source_id"], ["customer_data_sources.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "identity_type",
            "value_hash",
            name="uq_customer_identity_fingerprint",
        ),
    )
    op.create_table(
        "customer_consents",
        _uuid("id"),
        _uuid("company_id"),
        _uuid("profile_id"),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("channel", sa.String(16), server_default="all", nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("lawful_basis", sa.String(80), nullable=False),
        sa.Column("evidence_reference", sa.String(240), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        _uuid("recorded_by_user_id"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "purpose IN ('marketing', 'service', 'analytics', 'ai_processing', 'data_sharing')",
            name="ck_customer_consent_purpose",
        ),
        sa.CheckConstraint(
            "status IN ('granted', 'denied', 'revoked', 'expired')",
            name="ck_customer_consent_status",
        ),
        sa.CheckConstraint(
            "channel IN ('all', 'email', 'phone', 'whatsapp', 'sms', 'web')",
            name="ck_customer_consent_channel",
        ),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at > captured_at",
            name="ck_customer_consent_expiry",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["customer_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for table_name in TABLES:
        for column in ("company_id",):
            op.create_index(f"ix_{table_name}_{column}", table_name, [column])
    for table_name, columns in (
        ("customer_profiles", ("master_contact_id", "lifecycle_status")),
        ("customer_profile_contacts", ("profile_id", "contact_id")),
        ("customer_identities", ("profile_id", "data_source_id", "value_hash")),
        ("customer_consents", ("profile_id", "purpose", "status", "captured_at")),
    ):
        for column in columns:
            op.create_index(f"ix_{table_name}_{column}", table_name, [column])

    op.execute(
        sa.text(
            "INSERT INTO customer_data_sources "
            "(id, company_id, code, name, mode, status) "
            "SELECT gen_random_uuid(), company_id, 'orkestral_crm', "
            "'CRM Orkestral', 'system_of_record', 'active' "
            "FROM crm_contacts WHERE deleted_at IS NULL GROUP BY company_id "
            "ON CONFLICT (company_id, code) DO NOTHING"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO customer_profiles "
            "(id, company_id, master_contact_id, display_name, profile_type, "
            "lifecycle_status, quality_score) "
            "SELECT gen_random_uuid(), company_id, id, name, 'person', status, "
            "(CASE WHEN name IS NOT NULL THEN 20 ELSE 0 END + "
            "CASE WHEN email IS NOT NULL THEN 20 ELSE 0 END + "
            "CASE WHEN phone IS NOT NULL THEN 15 ELSE 0 END + "
            "CASE WHEN company_name IS NOT NULL THEN 15 ELSE 0 END + "
            "CASE WHEN job_title IS NOT NULL THEN 10 ELSE 0 END + "
            "CASE WHEN source IS NOT NULL THEN 10 ELSE 0 END + "
            "CASE WHEN assigned_user_id IS NOT NULL THEN 10 ELSE 0 END) "
            "FROM crm_contacts WHERE deleted_at IS NULL"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO customer_profile_contacts "
            "(company_id, profile_id, contact_id, link_role, match_confidence) "
            "SELECT company_id, id, master_contact_id, 'master', 100 "
            "FROM customer_profiles WHERE master_contact_id IS NOT NULL"
        )
    )
    system_role = str(op.get_bind().scalar(sa.text("SELECT current_user")))
    for table_name in TABLES:
        _tenant_rls(table_name, system_role)


def downgrade() -> None:
    for table_name in reversed(TABLES):
        op.drop_table(table_name)
