"""Add versioned agent governance and budgets.

Revision ID: 20260721_0032
Revises: 20260721_0031
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0032"
down_revision: str | None = "20260721_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("max_input_tokens", sa.Integer(), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("memory_enabled", sa.Boolean(), nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("autonomy_level", sa.Integer(), server_default="2", nullable=False),
        sa.Column("max_steps", sa.Integer(), server_default="12", nullable=False),
        sa.Column("max_runtime_seconds", sa.Integer(), server_default="120", nullable=False),
        sa.Column(
            "max_cost_per_run_microunits", sa.Integer(), server_default="1000000", nullable=False
        ),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("published_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'retired')", name="ck_agent_versions_status"
        ),
        sa.CheckConstraint("autonomy_level >= 0 AND autonomy_level <= 4", name="ck_agent_autonomy"),
        sa.CheckConstraint("max_steps > 0 AND max_steps <= 100", name="ck_agent_version_steps"),
        sa.CheckConstraint(
            "max_runtime_seconds > 0 AND max_runtime_seconds <= 3600",
            name="ck_agent_version_runtime",
        ),
        sa.CheckConstraint("max_cost_per_run_microunits >= 0", name="ck_agent_version_run_cost"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_version"),
    )
    op.create_index("ix_agent_versions_company_id", "agent_versions", ["company_id"])
    op.create_index("ix_agent_versions_agent_id", "agent_versions", ["agent_id"])
    op.create_index("ix_agent_versions_status", "agent_versions", ["status"])
    op.create_index(
        "ix_agent_versions_created_by_user_id", "agent_versions", ["created_by_user_id"]
    )
    op.create_index("ix_agent_versions_created_at", "agent_versions", ["created_at"])

    op.add_column(
        "agents", sa.Column("active_version_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_index("ix_agents_active_version_id", "agents", ["active_version_id"])
    op.execute(
        """
        INSERT INTO agent_versions (
            company_id, agent_id, version, status, instructions, provider, model, temperature,
            max_input_tokens, max_output_tokens, memory_enabled, knowledge_base_id,
            autonomy_level, max_steps, max_runtime_seconds, max_cost_per_run_microunits,
            checksum, created_by_user_id, published_by_user_id, created_at, published_at
        )
        SELECT company_id, id, 1, 'published', instructions, provider, model, temperature,
               max_input_tokens, max_output_tokens, memory_enabled, knowledge_base_id,
               2, 12, 120, 1000000,
               md5(id::text || ':' || updated_at::text), created_by_user_id, created_by_user_id,
               created_at, now()
        FROM agents
        """
    )
    op.execute(
        """
        UPDATE agents
        SET active_version_id = agent_versions.id
        FROM agent_versions
        WHERE agent_versions.agent_id = agents.id AND agent_versions.version = 1
        """
    )
    op.create_foreign_key(
        "fk_agents_active_version_id",
        "agents",
        "agent_versions",
        ["active_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "agent_budgets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("limit_microunits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reserved_microunits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("consumed_microunits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("hard_limit", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("cycle_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cycle_ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "limit_microunits >= 0 AND reserved_microunits >= 0 AND consumed_microunits >= 0",
            name="ck_agent_budget_amounts",
        ),
        sa.CheckConstraint("cycle_ends_at > cycle_started_at", name="ck_agent_budget_cycle"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", name="uq_agent_budgets_agent"),
    )
    op.create_index("ix_agent_budgets_company_id", "agent_budgets", ["company_id"])
    op.create_index("ix_agent_budgets_agent_id", "agent_budgets", ["agent_id"])
    op.execute(
        """
        INSERT INTO agent_budgets (company_id, agent_id, cycle_started_at, cycle_ends_at)
        SELECT company_id, id, now(), now() + interval '1 month' FROM agents
        """
    )

    op.add_column(
        "agent_tools",
        sa.Column("risk_level", sa.String(length=16), server_default="low", nullable=False),
    )
    op.execute("UPDATE agent_tools SET risk_level = 'high' WHERE is_sensitive = true")
    op.create_check_constraint(
        "ck_agent_tools_risk", "agent_tools", "risk_level IN ('low', 'medium', 'high', 'critical')"
    )
    op.add_column(
        "agent_tool_runs",
        sa.Column("agent_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_agent_tool_runs_agent_version_id", "agent_tool_runs", ["agent_version_id"])
    op.create_foreign_key(
        "fk_agent_tool_runs_version",
        "agent_tool_runs",
        "agent_versions",
        ["agent_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "agent_usage_records",
        sa.Column("agent_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_agent_usage_records_agent_version_id", "agent_usage_records", ["agent_version_id"]
    )
    op.create_foreign_key(
        "fk_agent_usage_records_version",
        "agent_usage_records",
        "agent_versions",
        ["agent_version_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_agent_usage_records_version", "agent_usage_records", type_="foreignkey")
    op.drop_index("ix_agent_usage_records_agent_version_id", table_name="agent_usage_records")
    op.drop_column("agent_usage_records", "agent_version_id")
    op.drop_constraint("fk_agent_tool_runs_version", "agent_tool_runs", type_="foreignkey")
    op.drop_index("ix_agent_tool_runs_agent_version_id", table_name="agent_tool_runs")
    op.drop_column("agent_tool_runs", "agent_version_id")
    op.drop_constraint("ck_agent_tools_risk", "agent_tools", type_="check")
    op.drop_column("agent_tools", "risk_level")
    op.drop_index("ix_agent_budgets_agent_id", table_name="agent_budgets")
    op.drop_index("ix_agent_budgets_company_id", table_name="agent_budgets")
    op.drop_table("agent_budgets")
    op.drop_constraint("fk_agents_active_version_id", "agents", type_="foreignkey")
    op.drop_index("ix_agents_active_version_id", table_name="agents")
    op.drop_column("agents", "active_version_id")
    op.drop_index("ix_agent_versions_created_at", table_name="agent_versions")
    op.drop_index("ix_agent_versions_created_by_user_id", table_name="agent_versions")
    op.drop_index("ix_agent_versions_status", table_name="agent_versions")
    op.drop_index("ix_agent_versions_agent_id", table_name="agent_versions")
    op.drop_index("ix_agent_versions_company_id", table_name="agent_versions")
    op.drop_table("agent_versions")
