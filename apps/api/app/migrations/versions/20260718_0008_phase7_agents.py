"""Adiciona agentes, ferramentas, conversas, ações e consumo.

Revision ID: 20260718_0008
Revises: 20260718_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260718_0008"
down_revision: str | None = "20260718_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def _indexes(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False, server_default="local"),
        sa.Column("model", sa.String(120), nullable=False, server_default="orkestral-local"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.2"),
        sa.Column("max_input_tokens", sa.Integer(), nullable=False, server_default="4096"),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False, server_default="1024"),
        sa.Column("memory_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("knowledge_base_id", UUID),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_agents_status"),
        sa.CheckConstraint("provider IN ('local', 'openai_compatible')", name="ck_agents_provider"),
        sa.CheckConstraint("temperature >= 0 AND temperature <= 2", name="ck_agents_temperature"),
        sa.CheckConstraint("max_input_tokens > 0 AND max_output_tokens > 0", name="ck_agents_token_limits"),
    )
    _indexes("agents", ("company_id", "created_by_user_id", "name", "status", "created_at"))

    op.create_table(
        "agent_tools",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", UUID, sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_key", sa.String(120), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("input_schema", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("required_permission", sa.String(120)),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("agent_id", "tool_key", name="uq_agent_tools_agent_key"),
    )
    _indexes("agent_tools", ("company_id", "agent_id", "tool_key", "enabled"))

    op.create_table(
        "agent_conversations",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", UUID, sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_agent_conversations_status"),
    )
    _indexes("agent_conversations", ("company_id", "agent_id", "user_id", "status", "created_at"))

    op.create_table(
        "agent_messages",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", UUID, sa.ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", UUID, sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_call", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("provider", sa.String(40)),
        sa.Column("model", sa.String(120)),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_microunits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('system', 'user', 'assistant', 'tool')", name="ck_agent_messages_role"),
        sa.CheckConstraint("input_tokens >= 0 AND output_tokens >= 0 AND total_tokens >= 0", name="ck_agent_messages_tokens"),
        sa.CheckConstraint("cost_microunits >= 0", name="ck_agent_messages_cost"),
    )
    _indexes("agent_messages", ("company_id", "conversation_id", "agent_id", "user_id", "role", "created_at"))

    op.create_table(
        "agent_tool_runs",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", UUID, sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", UUID, sa.ForeignKey("agent_conversations.id", ondelete="SET NULL")),
        sa.Column("message_id", UUID, sa.ForeignKey("agent_messages.id", ondelete="SET NULL")),
        sa.Column("tool_id", UUID, sa.ForeignKey("agent_tools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requested_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("state", sa.String(30), nullable=False, server_default="requested"),
        sa.Column("arguments", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_summary", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_summary", sa.Text()),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approved_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("rejected_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("rejected_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("state IN ('requested', 'awaiting_confirmation', 'approved', 'rejected', 'executing', 'completed', 'failed')", name="ck_agent_tool_runs_state"),
    )
    _indexes("agent_tool_runs", ("company_id", "agent_id", "conversation_id", "message_id", "tool_id", "requested_by_user_id", "state", "created_at"))

    op.create_table(
        "agent_usage_records",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("agent_id", UUID, sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", UUID, sa.ForeignKey("agent_conversations.id", ondelete="SET NULL")),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_microunits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_key", sa.String(120)),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_status", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("input_tokens >= 0 AND output_tokens >= 0 AND total_tokens >= 0", name="ck_agent_usage_tokens"),
        sa.CheckConstraint("cost_microunits >= 0", name="ck_agent_usage_cost"),
        sa.CheckConstraint("duration_ms >= 0", name="ck_agent_usage_duration"),
    )
    _indexes("agent_usage_records", ("company_id", "user_id", "agent_id", "conversation_id", "provider", "model", "tool_key", "result_status", "created_at"))


def downgrade() -> None:
    op.drop_table("agent_usage_records")
    op.drop_table("agent_tool_runs")
    op.drop_table("agent_messages")
    op.drop_table("agent_conversations")
    op.drop_table("agent_tools")
    op.drop_table("agents")
