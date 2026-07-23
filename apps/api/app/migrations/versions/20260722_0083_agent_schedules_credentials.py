"""Add versioned agent schedules, triggers and credential bindings.

Revision ID: 20260722_0083
Revises: 20260722_0082
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260722_0083"
down_revision: str | None = "20260722_0082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _indexes(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    op.create_table(
        "agent_execution_schedules",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("agent_version_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_key", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("objective", sa.String(1000), nullable=False),
        sa.Column("cadence_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "required_tool_keys",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("version >= 1", name="ck_agent_execution_schedule_version"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'paused', 'retired')",
            name="ck_agent_execution_schedule_status",
        ),
        sa.CheckConstraint(
            "cadence_minutes BETWEEN 5 AND 10080",
            name="ck_agent_execution_schedule_cadence",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "agent_id",
            "schedule_key",
            "version",
            name="uq_agent_execution_schedule_version",
        ),
    )
    _indexes(
        "agent_execution_schedules",
        (
            "company_id",
            "agent_id",
            "agent_version_id",
            "schedule_key",
            "next_run_at",
            "created_by_user_id",
            "published_by_user_id",
        ),
    )
    op.create_index(
        "ix_agent_execution_schedule_due",
        "agent_execution_schedules",
        ["status", "next_run_at", "company_id"],
    )

    op.create_table(
        "agent_event_triggers",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("agent_version_id", sa.Uuid(), nullable=False),
        sa.Column("trigger_key", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("event_type", sa.String(160), nullable=False),
        sa.Column("min_event_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("max_event_version", sa.Integer(), nullable=True),
        sa.Column("objective", sa.String(1000), nullable=False),
        sa.Column(
            "required_tool_keys",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("version >= 1", name="ck_agent_event_trigger_version"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'paused', 'retired')",
            name="ck_agent_event_trigger_status",
        ),
        sa.CheckConstraint("min_event_version >= 1", name="ck_agent_event_trigger_min_version"),
        sa.CheckConstraint(
            "max_event_version IS NULL OR max_event_version >= min_event_version",
            name="ck_agent_event_trigger_version_range",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "agent_id",
            "trigger_key",
            "version",
            name="uq_agent_event_trigger_version",
        ),
    )
    _indexes(
        "agent_event_triggers",
        (
            "company_id",
            "agent_id",
            "agent_version_id",
            "trigger_key",
            "event_type",
            "created_by_user_id",
            "published_by_user_id",
        ),
    )
    op.create_index(
        "ix_agent_event_trigger_match",
        "agent_event_triggers",
        ["status", "event_type", "company_id"],
    )

    op.create_table(
        "agent_credential_bindings",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("tool_key", sa.String(160), nullable=False),
        sa.Column("credential_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["credential_id"], ["integration_credentials.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "agent_id", "tool_key", name="uq_agent_credential_binding_tool"
        ),
    )
    _indexes(
        "agent_credential_bindings",
        ("company_id", "agent_id", "tool_key", "credential_id", "created_by_user_id"),
    )
    op.create_index(
        "ix_agent_credential_binding_lookup",
        "agent_credential_bindings",
        ["company_id", "agent_id", "enabled"],
    )

    op.create_table(
        "agent_runtime_dispatches",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("agent_version_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=True),
        sa.Column("trigger_id", sa.Uuid(), nullable=True),
        sa.Column("source_event_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason_code", sa.String(120), nullable=True),
        sa.Column("objective_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "required_tool_keys",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "credential_binding_ids",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "source_type IN ('schedule', 'event')", name="ck_agent_runtime_dispatch_source"
        ),
        sa.CheckConstraint(
            "status IN ('ready', 'blocked')", name="ck_agent_runtime_dispatch_status"
        ),
        sa.CheckConstraint(
            "(source_type = 'schedule' AND schedule_id IS NOT NULL AND trigger_id IS NULL) OR "
            "(source_type = 'event' AND trigger_id IS NOT NULL AND schedule_id IS NULL "
            "AND source_event_id IS NOT NULL)",
            name="ck_agent_runtime_dispatch_reference",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["schedule_id"], ["agent_execution_schedules.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["trigger_id"], ["agent_event_triggers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_event_id"], ["outbox_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "schedule_id", "scheduled_for", name="uq_agent_runtime_schedule_dispatch"
        ),
        sa.UniqueConstraint(
            "trigger_id", "source_event_id", name="uq_agent_runtime_event_dispatch"
        ),
    )
    _indexes(
        "agent_runtime_dispatches",
        (
            "company_id",
            "agent_id",
            "agent_version_id",
            "schedule_id",
            "trigger_id",
            "source_event_id",
            "source_type",
            "status",
            "scheduled_for",
        ),
    )
    op.create_index(
        "ix_agent_runtime_dispatch_queue",
        "agent_runtime_dispatches",
        ["status", "created_at", "company_id"],
    )


def downgrade() -> None:
    for table, indexes in (
        (
            "agent_runtime_dispatches",
            (
                "company_id",
                "agent_id",
                "agent_version_id",
                "schedule_id",
                "trigger_id",
                "source_event_id",
                "source_type",
                "status",
                "scheduled_for",
            ),
        ),
        (
            "agent_credential_bindings",
            ("company_id", "agent_id", "tool_key", "credential_id", "created_by_user_id"),
        ),
        (
            "agent_event_triggers",
            (
                "company_id",
                "agent_id",
                "agent_version_id",
                "trigger_key",
                "event_type",
                "created_by_user_id",
                "published_by_user_id",
            ),
        ),
        (
            "agent_execution_schedules",
            (
                "company_id",
                "agent_id",
                "agent_version_id",
                "schedule_key",
                "next_run_at",
                "created_by_user_id",
                "published_by_user_id",
            ),
        ),
    ):
        special = {
            "agent_runtime_dispatches": "ix_agent_runtime_dispatch_queue",
            "agent_credential_bindings": "ix_agent_credential_binding_lookup",
            "agent_event_triggers": "ix_agent_event_trigger_match",
            "agent_execution_schedules": "ix_agent_execution_schedule_due",
        }[table]
        op.drop_index(special, table_name=table)
        for column in reversed(indexes):
            op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_table(table)
