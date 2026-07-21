"""Add idempotent expiration reminders to reencryption legal holds.

Revision ID: 20260721_0065
Revises: 20260721_0064
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0065"
down_revision: str | None = "20260721_0064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "agent_memory_reencryption_legal_holds"
    op.add_column(
        table,
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_amr_legal_hold_reminder", table, ["reminder_sent_at"])


def downgrade() -> None:
    table = "agent_memory_reencryption_legal_holds"
    op.drop_index("ix_amr_legal_hold_reminder", table_name=table)
    op.drop_column(table, "reminder_sent_at")
