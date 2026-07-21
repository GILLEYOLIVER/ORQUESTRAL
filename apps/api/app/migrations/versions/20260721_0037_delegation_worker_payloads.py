"""Add encrypted delegation payloads and worker leases.

Revision ID: 20260721_0037
Revises: 20260721_0036
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0037"
down_revision: str | None = "20260721_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_delegations",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "agent_delegations", sa.Column("claimed_by", sa.String(length=160), nullable=True)
    )
    op.add_column(
        "agent_delegations",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_delegations", sa.Column("last_error_code", sa.String(length=80), nullable=True)
    )
    op.create_index(
        "ix_agent_delegations_lease_expires_at", "agent_delegations", ["lease_expires_at"]
    )
    op.create_table(
        "agent_delegation_payloads",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delegation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("encrypted_objective", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("destroyed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delegation_id"], ["agent_delegations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delegation_id", name="uq_agent_delegation_payload"),
    )
    for column in ("company_id", "delegation_id", "expires_at", "destroyed_at"):
        op.create_index(
            f"ix_agent_delegation_payloads_{column}", "agent_delegation_payloads", [column]
        )


def downgrade() -> None:
    for column in reversed(("company_id", "delegation_id", "expires_at", "destroyed_at")):
        op.drop_index(
            f"ix_agent_delegation_payloads_{column}", table_name="agent_delegation_payloads"
        )
    op.drop_table("agent_delegation_payloads")
    op.drop_index("ix_agent_delegations_lease_expires_at", table_name="agent_delegations")
    op.drop_column("agent_delegations", "last_error_code")
    op.drop_column("agent_delegations", "lease_expires_at")
    op.drop_column("agent_delegations", "claimed_by")
    op.drop_column("agent_delegations", "attempt_count")
