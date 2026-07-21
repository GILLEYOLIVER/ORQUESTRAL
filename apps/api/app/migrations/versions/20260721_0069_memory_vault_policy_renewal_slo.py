"""Add tenant vault policy, credential renewal and incident SLO.

Revision ID: 20260721_0069
Revises: 20260721_0068
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0069"
down_revision: str | None = "20260721_0068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_memory_vault_incidents",
        sa.Column("slo_breached_at", sa.DateTime(timezone=True)),
    )

    policy = "agent_memory_keyring_policies"
    op.create_table(
        policy,
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expiry_warning_days", sa.Integer(), nullable=False),
        sa.Column("automatic_exit_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("automatic_exit_batch_size", sa.Integer(), nullable=False),
        sa.Column("vault_failure_alert_threshold", sa.Integer(), nullable=False),
        sa.Column("vault_slo_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "updated_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("company_id", name="uq_agent_memory_keyring_policy_company"),
        sa.CheckConstraint(
            "expiry_warning_days BETWEEN 1 AND 90",
            name="ck_agent_memory_keyring_policy_warning",
        ),
        sa.CheckConstraint(
            "automatic_exit_batch_size BETWEEN 1 AND 500",
            name="ck_agent_memory_keyring_policy_batch",
        ),
        sa.CheckConstraint(
            "vault_failure_alert_threshold BETWEEN 1 AND 20",
            name="ck_agent_memory_keyring_policy_failure_threshold",
        ),
        sa.CheckConstraint(
            "vault_slo_minutes BETWEEN 1 AND 1440",
            name="ck_agent_memory_keyring_policy_slo",
        ),
    )
    op.create_index(f"ix_{policy}_company_id", policy, ["company_id"])
    op.create_index(f"ix_{policy}_updated_by_user_id", policy, ["updated_by_user_id"])

    renewal = "agent_memory_credential_renewals"
    op.create_table(
        renewal,
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "binding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_memory_keyring_bindings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "credential_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("integration_credentials.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("extension_days", sa.Integer(), nullable=False),
        sa.Column("reason_fingerprint", sa.String(64), nullable=False),
        sa.Column("proposed_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column(
            "requested_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "decided_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_agent_memory_credential_renewal_status",
        ),
        sa.CheckConstraint(
            "extension_days BETWEEN 1 AND 365",
            name="ck_agent_memory_credential_renewal_extension",
        ),
        sa.CheckConstraint(
            "char_length(reason_fingerprint) = 64",
            name="ck_agent_memory_credential_renewal_reason",
        ),
        sa.CheckConstraint(
            "decided_by_user_id IS NULL OR decided_by_user_id <> requested_by_user_id",
            name="ck_agent_memory_credential_renewal_separation",
        ),
    )
    for column in (
        "company_id",
        "agent_id",
        "binding_id",
        "credential_id",
        "status",
        "requested_by_user_id",
        "decided_by_user_id",
    ):
        op.create_index(f"ix_{renewal}_{column}", renewal, [column])
    op.create_index(
        "uq_agent_memory_credential_renewal_pending",
        renewal,
        ["company_id", "binding_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_table("agent_memory_credential_renewals")
    op.drop_table("agent_memory_keyring_policies")
    op.drop_column("agent_memory_vault_incidents", "slo_breached_at")
