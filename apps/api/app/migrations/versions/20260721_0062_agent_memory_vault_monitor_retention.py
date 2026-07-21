"""Bind external vault credentials and retain terminal memory jobs.

Revision ID: 20260721_0062
Revises: 20260721_0061
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0062"
down_revision: str | None = "20260721_0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "agent_memory_reencryption_jobs"
    op.add_column(table, sa.Column("vault_credential_id", postgresql.UUID(), nullable=True))
    op.add_column(table, sa.Column("vault_credential_fingerprint", sa.String(64), nullable=True))
    op.add_column(table, sa.Column("purge_after", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_agent_memory_reencryption_jobs_vault_credential_id",
        table,
        "integration_credentials",
        ["vault_credential_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(f"ix_{table}_vault_credential_id", table, ["vault_credential_id"])
    op.create_index(f"ix_{table}_purge_after", table, ["purge_after"])
    op.execute(
        sa.text(
            "UPDATE agent_memory_reencryption_jobs "
            "SET purge_after = COALESCE(closed_at, completed_at, updated_at) + INTERVAL '90 days' "
            "WHERE status IN ('completed', 'failed', 'closed')"
        )
    )
    op.create_check_constraint(
        "ck_agent_memory_reencryption_job_vault_binding",
        table,
        "(vault_credential_id IS NULL AND vault_credential_fingerprint IS NULL) OR "
        "(vault_credential_id IS NOT NULL AND char_length(vault_credential_fingerprint) = 64)",
    )
    op.create_check_constraint(
        "ck_agent_memory_reencryption_job_retention",
        table,
        "(status IN ('completed', 'failed', 'closed') AND purge_after IS NOT NULL) OR "
        "(status IN ('pending', 'running') AND purge_after IS NULL)",
    )


def downgrade() -> None:
    table = "agent_memory_reencryption_jobs"
    op.drop_constraint("ck_agent_memory_reencryption_job_retention", table, type_="check")
    op.drop_constraint("ck_agent_memory_reencryption_job_vault_binding", table, type_="check")
    op.drop_index(f"ix_{table}_purge_after", table_name=table)
    op.drop_index(f"ix_{table}_vault_credential_id", table_name=table)
    op.drop_constraint(
        "fk_agent_memory_reencryption_jobs_vault_credential_id", table, type_="foreignkey"
    )
    op.drop_column(table, "purge_after")
    op.drop_column(table, "vault_credential_fingerprint")
    op.drop_column(table, "vault_credential_id")
