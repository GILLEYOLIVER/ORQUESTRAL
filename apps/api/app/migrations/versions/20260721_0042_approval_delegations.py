"""Add temporal approval policies and absence delegations.

Revision ID: 20260721_0042
Revises: 20260721_0041
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0042"
down_revision: str | None = "20260721_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_approval_policy_versions",
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_approval_policy_versions",
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_agent_approval_policy_versions_effective_from",
        "agent_approval_policy_versions",
        ["effective_from"],
    )
    op.create_index(
        "ix_agent_approval_policy_versions_effective_until",
        "agent_approval_policy_versions",
        ["effective_until"],
    )
    op.create_check_constraint(
        "ck_agent_approval_policy_effective_range",
        "agent_approval_policy_versions",
        "effective_from IS NULL OR effective_until IS NULL OR effective_until > effective_from",
    )

    op.create_table(
        "approval_delegations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delegator_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delegate_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "delegator_user_id <> delegate_user_id",
            name="ck_approval_delegation_distinct_users",
        ),
        sa.CheckConstraint("ends_at > starts_at", name="ck_approval_delegation_time_range"),
        sa.CheckConstraint("status IN ('active', 'revoked')", name="ck_approval_delegation_status"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delegator_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delegate_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "delegator_user_id",
        "delegate_user_id",
        "starts_at",
        "ends_at",
        "status",
        "created_at",
    ):
        op.create_index(f"ix_approval_delegations_{column}", "approval_delegations", [column])

    op.add_column(
        "agent_delegation_approval_votes",
        sa.Column("represented_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        "UPDATE agent_delegation_approval_votes SET represented_user_id = user_id "
        "WHERE represented_user_id IS NULL"
    )
    op.alter_column("agent_delegation_approval_votes", "represented_user_id", nullable=False)
    op.create_foreign_key(
        "fk_agent_delegation_approval_votes_represented_user_id",
        "agent_delegation_approval_votes",
        "users",
        ["represented_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_agent_delegation_approval_votes_represented_user_id",
        "agent_delegation_approval_votes",
        ["represented_user_id"],
    )
    op.drop_constraint(
        "uq_agent_delegation_approval_vote",
        "agent_delegation_approval_votes",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_agent_delegation_approval_vote",
        "agent_delegation_approval_votes",
        ["delegation_approval_id", "policy_stage_id", "represented_user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_agent_delegation_approval_vote",
        "agent_delegation_approval_votes",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_agent_delegation_approval_vote",
        "agent_delegation_approval_votes",
        ["delegation_approval_id", "policy_stage_id", "user_id"],
    )
    op.drop_index(
        "ix_agent_delegation_approval_votes_represented_user_id",
        table_name="agent_delegation_approval_votes",
    )
    op.drop_constraint(
        "fk_agent_delegation_approval_votes_represented_user_id",
        "agent_delegation_approval_votes",
        type_="foreignkey",
    )
    op.drop_column("agent_delegation_approval_votes", "represented_user_id")

    op.drop_table("approval_delegations")
    op.drop_constraint(
        "ck_agent_approval_policy_effective_range",
        "agent_approval_policy_versions",
        type_="check",
    )
    op.drop_index(
        "ix_agent_approval_policy_versions_effective_until",
        table_name="agent_approval_policy_versions",
    )
    op.drop_index(
        "ix_agent_approval_policy_versions_effective_from",
        table_name="agent_approval_policy_versions",
    )
    op.drop_column("agent_approval_policy_versions", "effective_until")
    op.drop_column("agent_approval_policy_versions", "effective_from")
