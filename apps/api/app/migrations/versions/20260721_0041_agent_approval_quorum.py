"""Add staged agent approvals and quorum votes.

Revision ID: 20260721_0041
Revises: 20260721_0040
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0041"
down_revision: str | None = "20260721_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_approval_policy_stages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage_order", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("quorum", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("stage_order BETWEEN 1 AND 10", name="ck_agent_approval_stage_order"),
        sa.CheckConstraint("quorum BETWEEN 1 AND 20", name="ck_agent_approval_stage_quorum"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["policy_version_id"], ["agent_approval_policy_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "policy_version_id", "stage_order", name="uq_agent_approval_policy_stage_order"
        ),
    )
    op.create_index(
        "ix_agent_approval_policy_stages_company_id", "agent_approval_policy_stages", ["company_id"]
    )
    op.create_index(
        "ix_agent_approval_policy_stages_policy_version_id",
        "agent_approval_policy_stages",
        ["policy_version_id"],
    )
    op.create_table(
        "agent_approval_policy_stage_approvers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["stage_id"], ["agent_approval_policy_stages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stage_id", "user_id", name="uq_agent_approval_stage_approver"),
    )
    for column in ("company_id", "stage_id", "user_id"):
        op.create_index(
            f"ix_agent_approval_policy_stage_approvers_{column}",
            "agent_approval_policy_stage_approvers",
            [column],
        )
    op.add_column(
        "agent_delegation_approvals",
        sa.Column("current_policy_stage_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_delegation_approvals_current_policy_stage_id",
        "agent_delegation_approvals",
        "agent_approval_policy_stages",
        ["current_policy_stage_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_agent_delegation_approvals_current_policy_stage_id",
        "agent_delegation_approvals",
        ["current_policy_stage_id"],
    )
    op.create_table(
        "agent_delegation_approval_votes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delegation_approval_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_stage_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected')",
            name="ck_agent_delegation_approval_vote_decision",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["delegation_approval_id"], ["agent_delegation_approvals.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["policy_stage_id"], ["agent_approval_policy_stages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "delegation_approval_id",
            "policy_stage_id",
            "user_id",
            name="uq_agent_delegation_approval_vote",
        ),
    )
    for column in (
        "company_id",
        "delegation_approval_id",
        "policy_stage_id",
        "user_id",
        "created_at",
    ):
        op.create_index(
            f"ix_agent_delegation_approval_votes_{column}",
            "agent_delegation_approval_votes",
            [column],
        )
    op.drop_constraint("ck_approval_actions_action", "approval_actions", type_="check")
    op.create_check_constraint(
        "ck_approval_actions_action",
        "approval_actions",
        "action IN ('approved', 'rejected', 'commented', 'reminded', 'escalated', 'vote_approved', 'expired')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_approval_actions_action", "approval_actions", type_="check")
    op.create_check_constraint(
        "ck_approval_actions_action",
        "approval_actions",
        "action IN ('approved', 'rejected', 'commented', 'reminded', 'escalated', 'expired')",
    )
    op.drop_table("agent_delegation_approval_votes")
    op.drop_index(
        "ix_agent_delegation_approvals_current_policy_stage_id",
        table_name="agent_delegation_approvals",
    )
    op.drop_constraint(
        "fk_agent_delegation_approvals_current_policy_stage_id",
        "agent_delegation_approvals",
        type_="foreignkey",
    )
    op.drop_column("agent_delegation_approvals", "current_policy_stage_id")
    op.drop_table("agent_approval_policy_stage_approvers")
    op.drop_table("agent_approval_policy_stages")
