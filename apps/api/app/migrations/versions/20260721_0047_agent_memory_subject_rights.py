"""Add memory purposes and subject self-service metadata.

Revision ID: 20260721_0047
Revises: 20260721_0046
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0047"
down_revision: str | None = "20260721_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_memory_entries",
        sa.Column("purpose", sa.String(length=24), server_default="operations", nullable=False),
    )
    op.create_index("ix_agent_memory_entries_purpose", "agent_memory_entries", ["purpose"])
    op.create_check_constraint(
        "ck_agent_memory_purpose",
        "agent_memory_entries",
        "purpose IN ('service', 'personalization', 'operations', 'compliance', 'analytics')",
    )
    op.create_table(
        "agent_memory_purpose_policies",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.CheckConstraint(
            "purpose IN ('service', 'personalization', 'operations', 'compliance', 'analytics')",
            name="ck_agent_memory_purpose_policy_purpose",
        ),
        sa.CheckConstraint(
            "retention_days BETWEEN 1 AND 3650",
            name="ck_agent_memory_purpose_policy_retention",
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "purpose", name="uq_agent_memory_purpose_policy"),
    )
    for column in ("company_id", "agent_id", "purpose"):
        op.create_index(
            f"ix_agent_memory_purpose_policies_{column}",
            "agent_memory_purpose_policies",
            [column],
        )


def downgrade() -> None:
    op.drop_table("agent_memory_purpose_policies")
    op.drop_constraint("ck_agent_memory_purpose", "agent_memory_entries", type_="check")
    op.drop_index("ix_agent_memory_entries_purpose", table_name="agent_memory_entries")
    op.drop_column("agent_memory_entries", "purpose")
