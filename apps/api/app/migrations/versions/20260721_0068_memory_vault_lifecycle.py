"""Monitor managed keyrings and govern credential expiry.

Revision ID: 20260721_0068
Revises: 20260721_0067
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0068"
down_revision: str | None = "20260721_0067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    binding = "agent_memory_keyring_bindings"
    op.add_column(
        binding,
        sa.Column("health_status", sa.String(16), nullable=False, server_default="unknown"),
    )
    op.add_column(binding, sa.Column("last_health_checked_at", sa.DateTime(timezone=True)))
    op.add_column(binding, sa.Column("expiry_warning_sent_at", sa.DateTime(timezone=True)))
    op.add_column(binding, sa.Column("automatic_exit_started_at", sa.DateTime(timezone=True)))
    op.add_column(
        binding,
        sa.Column(
            "automatic_exit_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_memory_reencryption_jobs.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(binding, sa.Column("credential_revoked_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "ck_agent_memory_keyring_binding_health",
        binding,
        "health_status IN ('unknown', 'healthy', 'unavailable')",
    )
    op.create_index(
        "ix_agent_memory_keyring_bindings_health_status", binding, ["health_status"]
    )
    op.create_index(
        "ix_agent_memory_keyring_bindings_automatic_exit_job_id",
        binding,
        ["automatic_exit_job_id"],
    )

    incident = "agent_memory_vault_incidents"
    op.create_table(
        incident,
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
        sa.Column("provider_code", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "first_detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("alerted_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('open', 'resolved')", name="ck_agent_memory_vault_incident_status"
        ),
        sa.CheckConstraint(
            "failure_count >= 1", name="ck_agent_memory_vault_incident_failures"
        ),
        sa.CheckConstraint(
            "(status = 'open' AND resolved_at IS NULL) OR "
            "(status = 'resolved' AND resolved_at IS NOT NULL)",
            name="ck_agent_memory_vault_incident_resolution",
        ),
    )
    for column in (
        "company_id",
        "agent_id",
        "binding_id",
        "provider_code",
        "status",
        "first_detected_at",
    ):
        op.create_index(f"ix_agent_memory_vault_incidents_{column}", incident, [column])
    op.create_index(
        "uq_agent_memory_vault_incident_open",
        incident,
        ["company_id", "binding_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )


def downgrade() -> None:
    op.drop_table("agent_memory_vault_incidents")
    binding = "agent_memory_keyring_bindings"
    op.drop_index(
        "ix_agent_memory_keyring_bindings_automatic_exit_job_id", table_name=binding
    )
    op.drop_index("ix_agent_memory_keyring_bindings_health_status", table_name=binding)
    op.drop_constraint("ck_agent_memory_keyring_binding_health", binding, type_="check")
    for column in (
        "credential_revoked_at",
        "automatic_exit_job_id",
        "automatic_exit_started_at",
        "expiry_warning_sent_at",
        "last_health_checked_at",
        "health_status",
    ):
        op.drop_column(binding, column)
