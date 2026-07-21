"""Add tool policy, aggregate budgets, and blocked context alerts.

Revision ID: 20260721_0051
Revises: 20260721_0050
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0051"
down_revision: str | None = "20260721_0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_memory_policies",
        sa.Column("max_shared_context_entries", sa.Integer(), server_default="5", nullable=False),
    )
    op.add_column(
        "agent_memory_policies",
        sa.Column(
            "max_shared_context_characters", sa.Integer(), server_default="2000", nullable=False
        ),
    )
    op.add_column(
        "agent_memory_policies",
        sa.Column(
            "blocked_context_alert_threshold", sa.Integer(), server_default="3", nullable=False
        ),
    )
    op.create_check_constraint(
        "ck_agent_memory_policy_shared_entries",
        "agent_memory_policies",
        "max_shared_context_entries BETWEEN 1 AND 20",
    )
    op.create_check_constraint(
        "ck_agent_memory_policy_shared_characters",
        "agent_memory_policies",
        "max_shared_context_characters BETWEEN 64 AND 16000",
    )
    op.create_check_constraint(
        "ck_agent_memory_policy_blocked_alert",
        "agent_memory_policies",
        "blocked_context_alert_threshold BETWEEN 2 AND 20",
    )
    op.add_column(
        "agent_task_memory_access_grants",
        sa.Column(
            "allowed_tool_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE agent_task_memory_access_grants AS access_grant
        SET allowed_tool_keys = contract.allowed_tool_keys
        FROM agent_delegations AS delegation
        JOIN agent_task_contracts AS contract ON contract.id = delegation.contract_id
        WHERE access_grant.task_delegation_id = delegation.id
        """
    )
    op.drop_constraint(
        "ck_agent_task_memory_trace_outcome",
        "agent_task_memory_access_traces",
        type_="check",
    )
    op.create_check_constraint(
        "ck_agent_task_memory_trace_outcome",
        "agent_task_memory_access_traces",
        "outcome IN ('consumed', 'blocked', 'empty', 'revoked_before_use', "
        "'expired_before_use', 'tool_policy_denied', 'aggregate_limit_denied')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_agent_task_memory_trace_outcome",
        "agent_task_memory_access_traces",
        type_="check",
    )
    op.create_check_constraint(
        "ck_agent_task_memory_trace_outcome",
        "agent_task_memory_access_traces",
        "outcome IN ('consumed', 'blocked', 'empty', 'revoked_before_use', 'expired_before_use')",
    )
    op.drop_column("agent_task_memory_access_grants", "allowed_tool_keys")
    op.drop_constraint(
        "ck_agent_memory_policy_blocked_alert", "agent_memory_policies", type_="check"
    )
    op.drop_constraint(
        "ck_agent_memory_policy_shared_characters", "agent_memory_policies", type_="check"
    )
    op.drop_constraint(
        "ck_agent_memory_policy_shared_entries", "agent_memory_policies", type_="check"
    )
    op.drop_column("agent_memory_policies", "blocked_context_alert_threshold")
    op.drop_column("agent_memory_policies", "max_shared_context_characters")
    op.drop_column("agent_memory_policies", "max_shared_context_entries")
