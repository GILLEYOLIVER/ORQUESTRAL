"""Add agent approval escalation and audit action.

Revision ID: 20260721_0040
Revises: 20260721_0039
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0040"
down_revision: str | None = "20260721_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_approval_policy_versions",
        sa.Column("escalation_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "agent_approval_policy_versions",
        sa.Column("escalation_after_minutes", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_approval_policy_versions_escalation_user_id",
        "agent_approval_policy_versions",
        "users",
        ["escalation_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_agent_approval_policy_versions_escalation_user_id",
        "agent_approval_policy_versions",
        ["escalation_user_id"],
    )
    op.create_check_constraint(
        "ck_agent_approval_policy_escalation",
        "agent_approval_policy_versions",
        "(escalation_user_id IS NULL AND escalation_after_minutes IS NULL) OR "
        "(escalation_user_id IS NOT NULL AND assigned_user_id IS NOT NULL "
        "AND escalation_after_minutes BETWEEN 5 AND approval_ttl_minutes - 1 "
        "AND escalation_user_id <> assigned_user_id)",
    )
    op.create_check_constraint(
        "ck_agent_approval_policy_approvers_effect",
        "agent_approval_policy_versions",
        "effect = 'require_approval' OR "
        "(assigned_user_id IS NULL AND escalation_user_id IS NULL "
        "AND escalation_after_minutes IS NULL)",
    )

    op.add_column(
        "agent_delegation_approvals",
        sa.Column("escalation_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "agent_delegation_approvals",
        sa.Column("escalate_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_delegation_approvals",
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_delegation_approvals_escalation_user_id",
        "agent_delegation_approvals",
        "users",
        ["escalation_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_agent_delegation_approvals_escalation_user_id",
        "agent_delegation_approvals",
        ["escalation_user_id"],
    )
    op.create_index(
        "ix_agent_delegation_approvals_escalate_at",
        "agent_delegation_approvals",
        ["escalate_at"],
    )
    op.create_check_constraint(
        "ck_agent_delegation_approval_escalation",
        "agent_delegation_approvals",
        "(escalation_user_id IS NULL AND escalate_at IS NULL) OR "
        "(escalation_user_id IS NOT NULL AND escalate_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_agent_delegation_approval_escalation_deadline",
        "agent_delegation_approvals",
        "escalate_at IS NULL OR escalate_at < expires_at",
    )

    op.drop_constraint("ck_approval_actions_action", "approval_actions", type_="check")
    op.create_check_constraint(
        "ck_approval_actions_action",
        "approval_actions",
        "action IN ('approved', 'rejected', 'commented', 'reminded', 'escalated', 'expired')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_approval_actions_action", "approval_actions", type_="check")
    op.create_check_constraint(
        "ck_approval_actions_action",
        "approval_actions",
        "action IN ('approved', 'rejected', 'commented', 'reminded', 'expired')",
    )
    op.drop_constraint(
        "ck_agent_delegation_approval_escalation_deadline",
        "agent_delegation_approvals",
        type_="check",
    )
    op.drop_constraint(
        "ck_agent_delegation_approval_escalation",
        "agent_delegation_approvals",
        type_="check",
    )
    op.drop_index(
        "ix_agent_delegation_approvals_escalate_at",
        table_name="agent_delegation_approvals",
    )
    op.drop_index(
        "ix_agent_delegation_approvals_escalation_user_id",
        table_name="agent_delegation_approvals",
    )
    op.drop_constraint(
        "fk_agent_delegation_approvals_escalation_user_id",
        "agent_delegation_approvals",
        type_="foreignkey",
    )
    op.drop_column("agent_delegation_approvals", "escalated_at")
    op.drop_column("agent_delegation_approvals", "escalate_at")
    op.drop_column("agent_delegation_approvals", "escalation_user_id")

    op.drop_constraint(
        "ck_agent_approval_policy_approvers_effect",
        "agent_approval_policy_versions",
        type_="check",
    )
    op.drop_constraint(
        "ck_agent_approval_policy_escalation",
        "agent_approval_policy_versions",
        type_="check",
    )
    op.drop_index(
        "ix_agent_approval_policy_versions_escalation_user_id",
        table_name="agent_approval_policy_versions",
    )
    op.drop_constraint(
        "fk_agent_approval_policy_versions_escalation_user_id",
        "agent_approval_policy_versions",
        type_="foreignkey",
    )
    op.drop_column("agent_approval_policy_versions", "escalation_after_minutes")
    op.drop_column("agent_approval_policy_versions", "escalation_user_id")
