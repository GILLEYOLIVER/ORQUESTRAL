"""Adiciona notificacoes, preferencias e aprovacoes humanas.

Revision ID: 20260719_0015
Revises: 20260719_0014
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260719_0015"
down_revision: str | None = "20260719_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = (
    ("notifications.view", "notifications", "view", "Visualizar notificações"),
    ("notifications.manage", "notifications", "manage", "Administrar notificações"),
    ("approvals.view", "approvals", "view", "Visualizar aprovações"),
    ("approvals.decide", "approvals", "decide", "Decidir aprovações"),
)


def _id() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def upgrade() -> None:
    permission_table = sa.table(
        "permissions",
        sa.column("code", sa.String()),
        sa.column("module_code", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        permission_table,
        [
            {"code": code, "module_code": module, "action": action, "description": description}
            for code, module, action, description in PERMISSIONS
        ],
    )

    op.create_table(
        "notifications",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="info", nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=True),
        sa.Column("resource_id", sa.String(length=120), nullable=True),
        sa.Column(
            "data", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "channels",
            postgresql.JSONB(),
            server_default=sa.text("'[\"in_app\"]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "delivery_status",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'success', 'warning', 'error')",
            name="ck_notifications_severity",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "recipient_user_id",
        "event_type",
        "severity",
        "resource_type",
        "resource_id",
        "read_at",
        "archived_at",
        "created_at",
    ):
        op.create_index(f"ix_notifications_{column}", "notifications", [column])
    op.create_index(
        "ix_notifications_company_recipient_created",
        "notifications",
        ["company_id", "recipient_user_id", "created_at"],
    )

    op.create_table(
        "notification_preferences",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=120), server_default="*", nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("email_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("whatsapp_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("whatsapp_recipient", sa.String(length=40), nullable=True),
        sa.Column("reminders_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "user_id", "event_type", name="uq_notification_preferences_scope"
        ),
    )
    op.create_index(
        "ix_notification_preferences_company_id", "notification_preferences", ["company_id"]
    )
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"])

    op.create_table(
        "approval_requests",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workflow_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_tool_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("required_permission", sa.String(length=120), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "context", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("encrypted_payload", sa.LargeBinary(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "source_type IN ('workflow', 'agent', 'generic')",
            name="ck_approval_requests_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled', 'expired')",
            name="ck_approval_requests_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["workflow_execution_id"], ["workflow_executions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["agent_tool_run_id"], ["agent_tool_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "requested_by_user_id",
        "assigned_user_id",
        "workflow_id",
        "workflow_execution_id",
        "agent_tool_run_id",
        "source_type",
        "required_permission",
        "status",
        "reminder_at",
        "expires_at",
        "created_at",
    ):
        op.create_index(f"ix_approval_requests_{column}", "approval_requests", [column])
    op.create_index(
        "uq_approval_requests_pending_execution",
        "approval_requests",
        ["workflow_execution_id"],
        unique=True,
        postgresql_where=sa.text("workflow_execution_id IS NOT NULL AND status = 'pending'"),
    )
    op.create_index(
        "uq_approval_requests_pending_agent_run",
        "approval_requests",
        ["agent_tool_run_id"],
        unique=True,
        postgresql_where=sa.text("agent_tool_run_id IS NOT NULL AND status = 'pending'"),
    )

    op.create_table(
        "approval_actions",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "action IN ('approved', 'rejected', 'commented', 'reminded', 'expired')",
            name="ck_approval_actions_action",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["approval_request_id"], ["approval_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "approval_request_id",
        "actor_user_id",
        "action",
        "created_at",
    ):
        op.create_index(f"ix_approval_actions_{column}", "approval_actions", [column])


def downgrade() -> None:
    op.drop_table("approval_actions")
    op.drop_table("approval_requests")
    op.drop_table("notification_preferences")
    op.drop_table("notifications")
    for code, *_ in PERMISSIONS:
        op.execute(
            sa.text("DELETE FROM permissions WHERE code = :code").bindparams(code=code)
        )
