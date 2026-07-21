"""Bind memory risk signing versions to master key identifiers.

Revision ID: 20260721_0057
Revises: 20260721_0056
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0057"
down_revision: str | None = "20260721_0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "agent_memory_risk_signing_key_versions"
    op.add_column(table, sa.Column("master_key_id", sa.String(length=64), nullable=True))
    op.execute(
        sa.text("UPDATE agent_memory_risk_signing_key_versions SET master_key_id = 'legacy'")
    )
    op.alter_column(table, "master_key_id", nullable=False)
    op.create_check_constraint(
        "ck_agent_memory_risk_signing_master_key_id",
        table,
        "char_length(master_key_id) BETWEEN 6 AND 64",
    )
    op.create_index(f"ix_{table}_master_key_id", table, ["master_key_id"])


def downgrade() -> None:
    table = "agent_memory_risk_signing_key_versions"
    op.drop_index(f"ix_{table}_master_key_id", table_name=table)
    op.drop_constraint("ck_agent_memory_risk_signing_master_key_id", table, type_="check")
    op.drop_column(table, "master_key_id")
