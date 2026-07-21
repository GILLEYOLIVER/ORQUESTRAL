"""Add authorized agent memory retrieval controls.

Revision ID: 20260721_0044
Revises: 20260721_0043
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0044"
down_revision: str | None = "20260721_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_agent_security_event_source", "agent_security_events", type_="check")
    op.create_check_constraint(
        "ck_agent_security_event_source",
        "agent_security_events",
        "source IN ('user', 'knowledge', 'memory', 'provider', 'system')",
    )
    op.add_column(
        "agent_data_policies",
        sa.Column("allow_memory_egress", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "agent_memory_policies",
        sa.Column("retrieval_enabled", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "agent_memory_policies",
        sa.Column("max_retrieval_entries", sa.Integer(), server_default="5", nullable=False),
    )
    op.create_check_constraint(
        "ck_agent_memory_policy_retrieval_limit",
        "agent_memory_policies",
        "max_retrieval_entries BETWEEN 1 AND 20",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_agent_memory_policy_retrieval_limit", "agent_memory_policies", type_="check"
    )
    op.drop_column("agent_memory_policies", "max_retrieval_entries")
    op.drop_column("agent_memory_policies", "retrieval_enabled")
    op.drop_column("agent_data_policies", "allow_memory_egress")
    op.drop_constraint("ck_agent_security_event_source", "agent_security_events", type_="check")
    op.create_check_constraint(
        "ck_agent_security_event_source",
        "agent_security_events",
        "source IN ('user', 'knowledge', 'provider', 'system')",
    )
