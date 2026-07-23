"""Add multi-shift review coverage and holiday calendars.

Revision ID: 20260723_0090
Revises: 20260722_0089
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260723_0090"
down_revision: str | None = "20260722_0089"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "agent_dispatch_review_sla_policies"
    op.add_column(
        table,
        sa.Column(
            "on_call_shifts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        table,
        sa.Column(
            "holiday_calendar",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        table,
        sa.Column("minimum_coverage", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_check_constraint(
        "ck_agent_dispatch_review_sla_minimum_coverage",
        table,
        "minimum_coverage BETWEEN 1 AND 20",
    )


def downgrade() -> None:
    table = "agent_dispatch_review_sla_policies"
    op.drop_constraint(
        "ck_agent_dispatch_review_sla_minimum_coverage",
        table,
        type_="check",
    )
    op.drop_column(table, "minimum_coverage")
    op.drop_column(table, "holiday_calendar")
    op.drop_column(table, "on_call_shifts")
