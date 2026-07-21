"""Add vault retention, on-call window and identity canary.

Revision ID: 20260721_0071
Revises: 20260721_0070
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0071"
down_revision: str | None = "20260721_0070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    policy = "agent_memory_keyring_policies"
    op.add_column(
        policy,
        sa.Column("availability_retention_days", sa.Integer(), nullable=False, server_default="30"),
    )
    op.add_column(
        policy,
        sa.Column("on_call_timezone", sa.String(64), nullable=False, server_default="UTC"),
    )
    op.add_column(
        policy,
        sa.Column("on_call_start_hour", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        policy,
        sa.Column("on_call_end_hour", sa.Integer(), nullable=False, server_default="24"),
    )
    op.add_column(
        policy,
        sa.Column("identity_canary_days", sa.Integer(), nullable=False, server_default="14"),
    )
    op.add_column(
        policy,
        sa.Column(
            "identity_canary_interval_hours", sa.Integer(), nullable=False, server_default="24"
        ),
    )
    op.create_check_constraint(
        "ck_agent_memory_keyring_policy_availability_retention",
        policy,
        "availability_retention_days BETWEEN 7 AND 365",
    )
    op.create_check_constraint(
        "ck_agent_memory_keyring_policy_on_call_window",
        policy,
        "on_call_start_hour BETWEEN 0 AND 23 AND on_call_end_hour BETWEEN 1 AND 24 "
        "AND on_call_start_hour < on_call_end_hour",
    )
    op.create_check_constraint(
        "ck_agent_memory_keyring_policy_canary",
        policy,
        "identity_canary_days BETWEEN 1 AND 90 "
        "AND identity_canary_interval_hours BETWEEN 1 AND 168",
    )

    binding = "agent_memory_keyring_bindings"
    op.add_column(
        binding,
        sa.Column(
            "identity_canary_status", sa.String(16), nullable=False, server_default="unknown"
        ),
    )
    op.add_column(binding, sa.Column("last_identity_canary_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "ck_agent_memory_keyring_binding_canary",
        binding,
        "identity_canary_status IN ('unknown', 'healthy', 'unavailable')",
    )
    op.create_index(
        "ix_agent_memory_keyring_bindings_identity_canary_status",
        binding,
        ["identity_canary_status"],
    )


def downgrade() -> None:
    binding = "agent_memory_keyring_bindings"
    op.drop_index("ix_agent_memory_keyring_bindings_identity_canary_status", table_name=binding)
    op.drop_constraint("ck_agent_memory_keyring_binding_canary", binding, type_="check")
    op.drop_column(binding, "last_identity_canary_at")
    op.drop_column(binding, "identity_canary_status")

    policy = "agent_memory_keyring_policies"
    op.drop_constraint("ck_agent_memory_keyring_policy_canary", policy, type_="check")
    op.drop_constraint("ck_agent_memory_keyring_policy_on_call_window", policy, type_="check")
    op.drop_constraint(
        "ck_agent_memory_keyring_policy_availability_retention", policy, type_="check"
    )
    for column in (
        "identity_canary_interval_hours",
        "identity_canary_days",
        "on_call_end_hour",
        "on_call_start_hour",
        "on_call_timezone",
        "availability_retention_days",
    ):
        op.drop_column(policy, column)
