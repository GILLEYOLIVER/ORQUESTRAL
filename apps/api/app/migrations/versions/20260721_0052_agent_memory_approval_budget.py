"""Add classification approval and cost budget to shared memory.

Revision ID: 20260721_0052
Revises: 20260721_0051
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0052"
down_revision: str | None = "20260721_0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    grants = "agent_task_memory_access_grants"
    op.add_column(
        grants,
        sa.Column("max_classification", sa.String(24), server_default="internal", nullable=False),
    )
    op.add_column(
        grants,
        sa.Column("max_cost_microunits", sa.Integer(), server_default="1000", nullable=False),
    )
    op.add_column(
        grants,
        sa.Column("requires_human_approval", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        grants,
        sa.Column("approval_status", sa.String(16), server_default="not_required", nullable=False),
    )
    op.add_column(grants, sa.Column("approved_by_user_id", sa.Uuid(), nullable=True))
    op.add_column(
        grants, sa.Column("approval_decided_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_task_memory_access_approved_by",
        grants,
        "users",
        ["approved_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_agent_task_memory_access_grants_approval_status", grants, ["approval_status"]
    )
    op.create_index(
        "ix_agent_task_memory_access_grants_approved_by_user_id", grants, ["approved_by_user_id"]
    )
    op.create_check_constraint(
        "ck_agent_task_memory_access_approval_status",
        grants,
        "approval_status IN ('not_required', 'pending', 'approved', 'rejected')",
    )
    op.create_check_constraint(
        "ck_agent_task_memory_access_classification",
        grants,
        "max_classification IN ('public', 'internal', 'confidential', 'restricted')",
    )
    op.create_check_constraint(
        "ck_agent_task_memory_access_cost", grants, "max_cost_microunits BETWEEN 0 AND 2000000000"
    )
    op.create_check_constraint(
        "ck_agent_task_memory_access_approval",
        grants,
        "(requires_human_approval = false AND approval_status = 'not_required' AND approved_by_user_id IS NULL AND approval_decided_at IS NULL) OR (requires_human_approval = true AND ((approval_status = 'pending' AND approved_by_user_id IS NULL AND approval_decided_at IS NULL) OR (approval_status IN ('approved', 'rejected') AND approved_by_user_id IS NOT NULL AND approval_decided_at IS NOT NULL AND approved_by_user_id <> granted_by_user_id)))",
    )
    traces = "agent_task_memory_access_traces"
    op.add_column(
        traces,
        sa.Column("estimated_cost_microunits", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "ck_agent_task_memory_trace_cost", traces, "estimated_cost_microunits >= 0"
    )
    op.drop_constraint("ck_agent_task_memory_trace_outcome", traces, type_="check")
    op.create_check_constraint(
        "ck_agent_task_memory_trace_outcome",
        traces,
        "outcome IN ('consumed', 'blocked', 'empty', 'revoked_before_use', 'expired_before_use', 'tool_policy_denied', 'aggregate_limit_denied', 'cost_limit_denied')",
    )


def downgrade() -> None:
    traces = "agent_task_memory_access_traces"
    op.drop_constraint("ck_agent_task_memory_trace_outcome", traces, type_="check")
    op.create_check_constraint(
        "ck_agent_task_memory_trace_outcome",
        traces,
        "outcome IN ('consumed', 'blocked', 'empty', 'revoked_before_use', 'expired_before_use', 'tool_policy_denied', 'aggregate_limit_denied')",
    )
    op.drop_constraint("ck_agent_task_memory_trace_cost", traces, type_="check")
    op.drop_column(traces, "estimated_cost_microunits")
    grants = "agent_task_memory_access_grants"
    op.drop_constraint("ck_agent_task_memory_access_approval", grants, type_="check")
    op.drop_constraint("ck_agent_task_memory_access_cost", grants, type_="check")
    op.drop_constraint("ck_agent_task_memory_access_classification", grants, type_="check")
    op.drop_constraint("ck_agent_task_memory_access_approval_status", grants, type_="check")
    op.drop_index("ix_agent_task_memory_access_grants_approved_by_user_id", table_name=grants)
    op.drop_index("ix_agent_task_memory_access_grants_approval_status", table_name=grants)
    op.drop_constraint("fk_task_memory_access_approved_by", grants, type_="foreignkey")
    op.drop_column(grants, "approval_decided_at")
    op.drop_column(grants, "approved_by_user_id")
    op.drop_column(grants, "approval_status")
    op.drop_column(grants, "requires_human_approval")
    op.drop_column(grants, "max_cost_microunits")
    op.drop_column(grants, "max_classification")
