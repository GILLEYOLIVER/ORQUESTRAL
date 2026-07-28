"""marketing journey lifecycle, experiment evidence and agent recommendations

Revision ID: 20260727_0114
Revises: 20260727_0113
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260727_0114"
down_revision: str | None = "20260727_0113"
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
    op.drop_constraint(
        "ck_marketing_journey_steps_action_type",
        "marketing_journey_steps",
        type_="check",
    )
    op.create_check_constraint(
        "ck_marketing_journey_steps_action_type",
        "marketing_journey_steps",
        "action_type IN ('wait', 'email', 'whatsapp', 'sms', 'task', 'webhook')",
    )
    op.create_table(
        "marketing_journey_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("journey_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="published", nullable=False),
        sa.Column("definition_json", postgresql.JSONB(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("published_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_marketing_journey_versions_version"),
        sa.CheckConstraint("status IN ('published','retired')", name="ck_marketing_journey_versions_status"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["journey_id"], ["marketing_journeys.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("journey_id", "version", name="uq_marketing_journey_versions_number"),
    )
    op.create_table(
        "marketing_journey_simulations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("journey_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("definition_checksum", sa.String(64), nullable=False),
        sa.Column("input_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("trace_json", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("issues_json", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('passed','failed')", name="ck_marketing_journey_simulations_status"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["journey_id"], ["marketing_journeys.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "marketing_experiment_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant_key", sa.String(80), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("metric_value", sa.Numeric(18, 6), nullable=False),
        sa.Column("confidence", sa.Numeric(8, 6), nullable=False),
        sa.Column("source_rule", sa.String(120), nullable=False),
        sa.Column("source_reference", sa.String(240), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("sample_size >= 0", name="ck_marketing_experiment_evidence_sample"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["experiment_id"], ["marketing_experiments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id", "variant_key", name="uq_marketing_experiment_evidence_variant"),
    )
    op.create_table(
        "marketing_agent_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recommendation_type", sa.String(80), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("evidence_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), server_default="proposed", nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('proposed','approved','dismissed')", name="ck_marketing_agent_recommendations_status"),
        sa.CheckConstraint("risk_level IN ('low','medium','high')", name="ck_marketing_agent_recommendations_risk"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["marketing_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    indexes = {
        "marketing_journey_versions": ("company_id", "journey_id", "status", "checksum", "published_by_user_id"),
        "marketing_journey_simulations": ("company_id", "journey_id", "status", "definition_checksum", "requested_by_user_id", "created_at"),
        "marketing_experiment_evidence": ("company_id", "experiment_id", "variant_key"),
        "marketing_agent_recommendations": ("company_id", "campaign_id", "agent_id", "agent_version_id", "recommendation_type", "status", "requested_by_user_id", "decided_by_user_id"),
    }
    for table, columns in indexes.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])
        _rls(table)
    op.create_index(
        "ix_marketing_journey_simulations_company_journey",
        "marketing_journey_simulations",
        ["company_id", "journey_id", "created_at"],
    )
    op.create_index(
        "ix_marketing_agent_recommendations_company_status",
        "marketing_agent_recommendations",
        ["company_id", "status"],
    )


def downgrade() -> None:
    for table in (
        "marketing_agent_recommendations",
        "marketing_experiment_evidence",
        "marketing_journey_simulations",
        "marketing_journey_versions",
    ):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.drop_table(table)
    op.drop_constraint(
        "ck_marketing_journey_steps_action_type",
        "marketing_journey_steps",
        type_="check",
    )
    op.create_check_constraint(
        "ck_marketing_journey_steps_action_type",
        "marketing_journey_steps",
        "action_type IN ('wait', 'email', 'whatsapp', 'task', 'webhook')",
    )
