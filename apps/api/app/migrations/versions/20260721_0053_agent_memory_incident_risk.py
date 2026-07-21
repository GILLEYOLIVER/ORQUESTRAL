"""Add approval expiry, incident revocation and memory risk records.

Revision ID: 20260721_0053
Revises: 20260721_0052
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0053"
down_revision: str | None = "20260721_0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    incidents = "agent_task_memory_access_incidents"
    op.create_table(
        incidents,
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("owner_agent_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("incident_reference_fingerprint", sa.String(64), nullable=False),
        sa.Column("reason_fingerprint", sa.String(64), nullable=False),
        sa.Column("revoked_grants", sa.Integer(), server_default="0", nullable=False),
        sa.Column("triggered_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "revoked_grants >= 0", name="ck_agent_task_memory_incident_revoked_grants"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "idempotency_key", name="uq_agent_task_memory_incident_idempotency"
        ),
    )
    for column in (
        "company_id",
        "owner_agent_id",
        "idempotency_key",
        "triggered_by_user_id",
        "created_at",
    ):
        op.create_index(f"ix_{incidents}_{column}", incidents, [column])

    grants = "agent_task_memory_access_grants"
    op.add_column(grants, sa.Column("approval_ttl_minutes", sa.Integer(), nullable=True))
    op.add_column(
        grants, sa.Column("approval_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(grants, sa.Column("revocation_incident_id", sa.Uuid(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE agent_task_memory_access_grants "
            "SET approval_ttl_minutes = 30, "
            "approval_expires_at = LEAST(expires_at, created_at + interval '30 minutes') "
            "WHERE requires_human_approval = true"
        )
    )
    op.create_check_constraint(
        "ck_agent_task_memory_access_approval_expiration",
        grants,
        "(requires_human_approval = false AND approval_ttl_minutes IS NULL "
        "AND approval_expires_at IS NULL) OR "
        "(requires_human_approval = true AND approval_ttl_minutes BETWEEN 5 AND 240 "
        "AND approval_expires_at IS NOT NULL AND approval_expires_at > created_at "
        "AND approval_expires_at <= expires_at)",
    )
    op.create_foreign_key(
        "fk_task_memory_access_revocation_incident",
        grants,
        incidents,
        ["revocation_incident_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_agent_task_memory_access_grants_approval_expires_at", grants, ["approval_expires_at"]
    )
    op.create_index(
        "ix_agent_task_memory_access_grants_revocation_incident_id",
        grants,
        ["revocation_incident_id"],
    )


def downgrade() -> None:
    grants = "agent_task_memory_access_grants"
    op.drop_index("ix_agent_task_memory_access_grants_revocation_incident_id", table_name=grants)
    op.drop_index("ix_agent_task_memory_access_grants_approval_expires_at", table_name=grants)
    op.drop_constraint("fk_task_memory_access_revocation_incident", grants, type_="foreignkey")
    op.drop_constraint("ck_agent_task_memory_access_approval_expiration", grants, type_="check")
    op.drop_column(grants, "revocation_incident_id")
    op.drop_column(grants, "approval_expires_at")
    op.drop_column(grants, "approval_ttl_minutes")
    incidents = "agent_task_memory_access_incidents"
    for column in reversed(
        ("company_id", "owner_agent_id", "idempotency_key", "triggered_by_user_id", "created_at")
    ):
        op.drop_index(f"ix_{incidents}_{column}", table_name=incidents)
    op.drop_table(incidents)
