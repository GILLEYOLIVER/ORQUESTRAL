"""Add scoped memory policies and conversation lifecycle.

Revision ID: 20260721_0046
Revises: 20260721_0045
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0046"
down_revision: str | None = "20260721_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_memory_policies",
        sa.Column("max_context_tokens", sa.Integer(), server_default="1000", nullable=False),
    )
    op.create_check_constraint(
        "ck_agent_memory_policy_context_tokens",
        "agent_memory_policies",
        "max_context_tokens BETWEEN 128 AND 16000",
    )
    op.create_table(
        "agent_memory_scope_policies",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=24), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("retrieval_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.CheckConstraint(
            "scope IN ('conversation', 'task', 'user', 'company', 'operational')",
            name="ck_agent_memory_scope_policy_scope",
        ),
        sa.CheckConstraint(
            "retention_days BETWEEN 1 AND 3650",
            name="ck_agent_memory_scope_policy_retention",
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "scope", name="uq_agent_memory_scope_policy"),
    )
    for column in ("company_id", "agent_id", "scope"):
        op.create_index(
            f"ix_agent_memory_scope_policies_{column}",
            "agent_memory_scope_policies",
            [column],
        )
    op.add_column("agent_conversations", sa.Column("closed_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE agent_conversations SET closed_at = updated_at WHERE status = 'closed'")
    op.create_index("ix_agent_conversations_closed_at", "agent_conversations", ["closed_at"])
    op.create_check_constraint(
        "ck_agent_conversations_closed_at",
        "agent_conversations",
        "(status = 'open' AND closed_at IS NULL) OR (status = 'closed' AND closed_at IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_agent_conversations_closed_at", "agent_conversations", type_="check")
    op.drop_index("ix_agent_conversations_closed_at", table_name="agent_conversations")
    op.drop_column("agent_conversations", "closed_at")
    op.drop_table("agent_memory_scope_policies")
    op.drop_constraint(
        "ck_agent_memory_policy_context_tokens", "agent_memory_policies", type_="check"
    )
    op.drop_column("agent_memory_policies", "max_context_tokens")
