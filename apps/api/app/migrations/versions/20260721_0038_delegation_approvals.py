"""Add encrypted human approvals for delegated tools.

Revision ID: 20260721_0038
Revises: 20260721_0037
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0038"
down_revision: str | None = "20260721_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_agent_delegation_status", "agent_delegations", type_="check")
    op.create_check_constraint(
        "ck_agent_delegation_status",
        "agent_delegations",
        "status IN ('queued', 'in_progress', 'awaiting_approval', 'completed', 'failed', 'cancelled')",
    )
    op.create_table(
        "agent_delegation_approvals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delegation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("encrypted_arguments", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired')",
            name="ck_agent_delegation_approval_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delegation_id"], ["agent_delegations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["approval_request_id"], ["approval_requests.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["tool_id"], ["agent_tools.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approval_request_id", name="uq_agent_delegation_approval_request"),
    )
    for column in (
        "company_id",
        "delegation_id",
        "approval_request_id",
        "tool_id",
        "status",
        "requested_by_user_id",
        "expires_at",
        "created_at",
    ):
        op.create_index(
            f"ix_agent_delegation_approvals_{column}",
            "agent_delegation_approvals",
            [column],
        )


def downgrade() -> None:
    for column in reversed(
        (
            "company_id",
            "delegation_id",
            "approval_request_id",
            "tool_id",
            "status",
            "requested_by_user_id",
            "expires_at",
            "created_at",
        )
    ):
        op.drop_index(
            f"ix_agent_delegation_approvals_{column}",
            table_name="agent_delegation_approvals",
        )
    op.drop_table("agent_delegation_approvals")
    op.drop_constraint("ck_agent_delegation_status", "agent_delegations", type_="check")
    op.create_check_constraint(
        "ck_agent_delegation_status",
        "agent_delegations",
        "status IN ('queued', 'in_progress', 'completed', 'failed', 'cancelled')",
    )
