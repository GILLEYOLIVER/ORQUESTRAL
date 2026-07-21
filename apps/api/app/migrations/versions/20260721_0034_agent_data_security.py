"""Add agent data egress policies and security events.

Revision ID: 20260721_0034
Revises: 20260721_0033
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0034"
down_revision: str | None = "20260721_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_data_policies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "allowed_provider_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[\"local\"]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "external_processing_enabled", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("allow_message_egress", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("allow_knowledge_egress", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("redact_sensitive_data", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "max_data_classification",
            sa.String(length=20),
            server_default="confidential",
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "max_data_classification IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_agent_data_policy_classification",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", name="uq_agent_data_policies_agent"),
    )
    op.create_index("ix_agent_data_policies_company_id", "agent_data_policies", ["company_id"])
    op.create_index("ix_agent_data_policies_agent_id", "agent_data_policies", ["agent_id"])
    op.execute(
        """
        INSERT INTO agent_data_policies (
            company_id, agent_id, allowed_provider_keys, external_processing_enabled,
            allow_message_egress, allow_knowledge_egress
        )
        SELECT company_id, id, jsonb_build_array(provider), provider <> 'local',
               provider <> 'local', provider <> 'local'
        FROM agents
        """
    )

    op.create_table(
        "agent_security_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "indicators",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "category IN ('prompt_injection', 'data_egress', 'sensitive_data')",
            name="ck_agent_security_event_category",
        ),
        sa.CheckConstraint(
            "source IN ('user', 'knowledge', 'provider', 'system')",
            name="ck_agent_security_event_source",
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_agent_security_event_severity",
        ),
        sa.CheckConstraint(
            "action IN ('blocked', 'redacted', 'reported')", name="ck_agent_security_event_action"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "agent_id",
        "agent_run_id",
        "category",
        "source",
        "severity",
        "action",
        "content_fingerprint",
        "created_at",
    ):
        op.create_index(f"ix_agent_security_events_{column}", "agent_security_events", [column])


def downgrade() -> None:
    for column in reversed(
        (
            "company_id",
            "agent_id",
            "agent_run_id",
            "category",
            "source",
            "severity",
            "action",
            "content_fingerprint",
            "created_at",
        )
    ):
        op.drop_index(f"ix_agent_security_events_{column}", table_name="agent_security_events")
    op.drop_table("agent_security_events")
    op.drop_index("ix_agent_data_policies_agent_id", table_name="agent_data_policies")
    op.drop_index("ix_agent_data_policies_company_id", table_name="agent_data_policies")
    op.drop_table("agent_data_policies")
