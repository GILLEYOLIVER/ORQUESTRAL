"""Bind task memory to delegations and add approved legal retention.

Revision ID: 20260721_0048
Revises: 20260721_0047
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0048"
down_revision: str | None = "20260721_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_memory_entries",
        sa.Column("task_delegation_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_memory_entries_task_delegation",
        "agent_memory_entries",
        "agent_delegations",
        ["task_delegation_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_agent_memory_entries_task_delegation_id",
        "agent_memory_entries",
        ["task_delegation_id"],
    )
    op.execute("UPDATE agent_memory_entries SET scope = 'operational' WHERE scope = 'task'")
    op.create_check_constraint(
        "ck_agent_memory_task_delegation_required",
        "agent_memory_entries",
        "scope <> 'task' OR task_delegation_id IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_agent_memory_task_delegation_scope",
        "agent_memory_entries",
        "scope = 'task' OR task_delegation_id IS NULL",
    )

    op.create_table(
        "agent_memory_legal_holds",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("task_delegation_id", sa.Uuid(), nullable=False),
        sa.Column("reason_code", sa.String(length=32), nullable=False),
        sa.Column("legal_reference_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("decided_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_agent_memory_legal_hold_status",
        ),
        sa.CheckConstraint(
            "reason_code IN ('legal_claim', 'regulatory_request', 'audit_preservation')",
            name="ck_agent_memory_legal_hold_reason",
        ),
        sa.CheckConstraint(
            "retention_days BETWEEN 1 AND 3650",
            name="ck_agent_memory_legal_hold_retention",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_agent_memory_legal_hold_expiration",
        ),
        sa.CheckConstraint(
            "decided_by_user_id IS NULL OR decided_by_user_id <> requested_by_user_id",
            name="ck_agent_memory_legal_hold_separation",
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND decided_by_user_id IS NULL AND decided_at IS NULL) OR "
            "(status IN ('approved', 'rejected') AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL)",
            name="ck_agent_memory_legal_hold_decision",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["task_delegation_id"], ["agent_delegations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "agent_id",
        "task_delegation_id",
        "reason_code",
        "legal_reference_fingerprint",
        "status",
        "requested_by_user_id",
        "decided_by_user_id",
        "expires_at",
        "created_at",
    ):
        op.create_index(
            f"ix_agent_memory_legal_holds_{column}",
            "agent_memory_legal_holds",
            [column],
        )


def downgrade() -> None:
    op.drop_table("agent_memory_legal_holds")
    op.drop_constraint(
        "ck_agent_memory_task_delegation_scope", "agent_memory_entries", type_="check"
    )
    op.drop_constraint(
        "ck_agent_memory_task_delegation_required", "agent_memory_entries", type_="check"
    )
    op.drop_index("ix_agent_memory_entries_task_delegation_id", table_name="agent_memory_entries")
    op.drop_constraint(
        "fk_agent_memory_entries_task_delegation", "agent_memory_entries", type_="foreignkey"
    )
    op.drop_column("agent_memory_entries", "task_delegation_id")
