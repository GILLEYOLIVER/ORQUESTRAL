"""Adiciona workflows e execuções integrados ao n8n.

Revision ID: 20260718_0007
Revises: 20260718_0006
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260718_0007"
down_revision: str | None = "20260718_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("created_by_user_id", UUID, nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("definition", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("n8n_workflow_id", sa.String(80), nullable=True),
        sa.Column("n8n_version_id", sa.String(80), nullable=True),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("sync_status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("internal_webhook_path", sa.String(160), nullable=False),
        sa.Column("public_webhook_key", sa.String(120), nullable=False),
        sa.Column("encrypted_webhook_secret", sa.LargeBinary(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("published_at", TIMESTAMP, nullable=True),
        sa.Column("created_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'active', 'inactive', 'error')", name="ck_workflows_status"),
        sa.CheckConstraint("sync_status IN ('pending', 'synced', 'error')", name="ck_workflows_sync_status"),
        sa.CheckConstraint("version >= 1", name="ck_workflows_version"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("internal_webhook_path"),
        sa.UniqueConstraint("n8n_workflow_id"),
        sa.UniqueConstraint("public_webhook_key"),
    )
    for column in ("company_id", "created_by_user_id", "name", "n8n_workflow_id", "status", "sync_status", "public_webhook_key", "created_at"):
        op.create_index(f"ix_workflows_{column}", "workflows", [column])

    op.create_table(
        "workflow_executions",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("workflow_id", UUID, nullable=False),
        sa.Column("requested_by_user_id", UUID, nullable=True),
        sa.Column("external_execution_id", sa.String(80), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="queued", nullable=False),
        sa.Column("input_summary", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("output_summary", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", TIMESTAMP, nullable=True),
        sa.Column("finished_at", TIMESTAMP, nullable=True),
        sa.Column("created_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source IN ('manual', 'webhook', 'schedule', 'system')", name="ck_workflow_executions_source"),
        sa.CheckConstraint("status IN ('queued', 'running', 'success', 'error', 'canceled', 'waiting')", name="ck_workflow_executions_status"),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_workflow_executions_duration"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("company_id", "workflow_id", "requested_by_user_id", "external_execution_id", "source", "status", "created_at"):
        op.create_index(f"ix_workflow_executions_{column}", "workflow_executions", [column])


def downgrade() -> None:
    op.drop_table("workflow_executions")
    op.drop_table("workflows")
