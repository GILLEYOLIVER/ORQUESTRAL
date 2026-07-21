"""Add vault on-call, availability history and identity rotation.

Revision ID: 20260721_0070
Revises: 20260721_0069
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0070"
down_revision: str | None = "20260721_0069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_memory_keyring_policies",
        sa.Column(
            "on_call_user_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    availability = "agent_memory_vault_availability_windows"
    op.create_table(
        availability,
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
        sa.Column("provider_code", sa.String(64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_checks", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("successful_checks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_checks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("slo_breaches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "company_id",
            "provider_code",
            "window_started_at",
            name="uq_agent_memory_vault_availability_window",
        ),
        sa.CheckConstraint(
            "total_checks >= 1 AND successful_checks >= 0 AND failed_checks >= 0 "
            "AND total_checks = successful_checks + failed_checks",
            name="ck_agent_memory_vault_availability_counts",
        ),
        sa.CheckConstraint("slo_breaches >= 0", name="ck_agent_memory_vault_availability_slo"),
    )
    for column in ("company_id", "provider_code", "window_started_at"):
        op.create_index(f"ix_{availability}_{column}", availability, [column])

    rotation = "agent_memory_workload_identity_rotations"
    op.create_table(
        rotation,
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
        sa.Column("provider_code", sa.String(64), nullable=False),
        sa.Column("encrypted_identity_reference", sa.LargeBinary(), nullable=False),
        sa.Column("previous_identity_fingerprint", sa.String(64), nullable=False),
        sa.Column("proposed_identity_fingerprint", sa.String(64), nullable=False),
        sa.Column("reason_fingerprint", sa.String(64), nullable=False),
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
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_agent_memory_workload_identity_rotation_status",
        ),
        sa.CheckConstraint(
            "char_length(previous_identity_fingerprint) = 64 "
            "AND char_length(proposed_identity_fingerprint) = 64 "
            "AND char_length(reason_fingerprint) = 64",
            name="ck_agent_memory_workload_identity_rotation_fingerprints",
        ),
        sa.CheckConstraint(
            "decided_by_user_id IS NULL OR decided_by_user_id <> requested_by_user_id",
            name="ck_agent_memory_workload_identity_rotation_separation",
        ),
    )
    for name, column in (
        ("ix_am_wir_company", "company_id"),
        ("ix_am_wir_agent", "agent_id"),
        ("ix_am_wir_binding", "binding_id"),
        ("ix_am_wir_credential", "credential_id"),
        ("ix_am_wir_provider", "provider_code"),
        ("ix_am_wir_status", "status"),
        ("ix_am_wir_requester", "requested_by_user_id"),
        ("ix_am_wir_decider", "decided_by_user_id"),
    ):
        op.create_index(name, rotation, [column])
    op.create_index(
        "uq_agent_memory_workload_identity_rotation_pending",
        rotation,
        ["company_id", "binding_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_table("agent_memory_workload_identity_rotations")
    op.drop_table("agent_memory_vault_availability_windows")
    op.drop_column("agent_memory_keyring_policies", "on_call_user_ids")
