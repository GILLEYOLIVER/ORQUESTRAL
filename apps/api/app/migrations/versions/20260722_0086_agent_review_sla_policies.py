"""Add versioned agent review SLA policies.

Revision ID: 20260722_0086
Revises: 20260722_0085
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260722_0086"
down_revision: str | None = "20260722_0085"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_dispatch_review_sla_policies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("sla_minutes", sa.Integer(), nullable=False),
        sa.Column("escalation_minutes", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "published_by_user_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("version >= 1", name="ck_agent_dispatch_review_sla_version"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'retired')",
            name="ck_agent_dispatch_review_sla_status",
        ),
        sa.CheckConstraint(
            "sla_minutes BETWEEN 5 AND 10080",
            name="ck_agent_dispatch_review_sla_minutes",
        ),
        sa.CheckConstraint(
            "escalation_minutes > sla_minutes AND escalation_minutes <= 20160",
            name="ck_agent_dispatch_review_sla_escalation",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["published_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "agent_id",
            "version",
            name="uq_agent_dispatch_review_sla_version",
        ),
    )
    op.create_index(
        "ix_agent_dispatch_review_sla_company",
        "agent_dispatch_review_sla_policies",
        ["company_id"],
    )
    op.create_index(
        "ix_agent_dispatch_review_sla_agent",
        "agent_dispatch_review_sla_policies",
        ["agent_id"],
    )
    op.create_index(
        "uq_agent_dispatch_review_sla_published",
        "agent_dispatch_review_sla_policies",
        ["company_id", "agent_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
    )


def downgrade() -> None:
    op.drop_table("agent_dispatch_review_sla_policies")
