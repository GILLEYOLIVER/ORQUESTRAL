"""Add cooperative cancellation and compensation state to workflow executions.

Revision ID: 20260722_0079
Revises: 20260721_0078
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260722_0079"
down_revision: str | None = "20260721_0078"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workflow_executions",
        sa.Column("canceled_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "workflow_executions", sa.Column("cancel_reason", sa.String(length=300), nullable=True)
    )
    op.add_column(
        "workflow_executions",
        sa.Column(
            "compensation_status",
            sa.String(length=24),
            server_default="not_required",
            nullable=False,
        ),
    )
    op.add_column(
        "workflow_executions",
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "workflow_executions",
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_workflow_execution_canceled_by_user",
        "workflow_executions",
        "users",
        ["canceled_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_workflow_executions_canceled_by_user_id",
        "workflow_executions",
        ["canceled_by_user_id"],
    )
    op.create_index(
        "ix_workflow_executions_compensation_status",
        "workflow_executions",
        ["compensation_status"],
    )
    op.create_check_constraint(
        "ck_workflow_executions_compensation_status",
        "workflow_executions",
        "compensation_status IN ('not_required', 'pending', 'acknowledged')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_workflow_executions_compensation_status",
        "workflow_executions",
        type_="check",
    )
    op.drop_index("ix_workflow_executions_compensation_status", table_name="workflow_executions")
    op.drop_index("ix_workflow_executions_canceled_by_user_id", table_name="workflow_executions")
    op.drop_constraint(
        "fk_workflow_execution_canceled_by_user",
        "workflow_executions",
        type_="foreignkey",
    )
    op.drop_column("workflow_executions", "canceled_at")
    op.drop_column("workflow_executions", "cancellation_requested_at")
    op.drop_column("workflow_executions", "compensation_status")
    op.drop_column("workflow_executions", "cancel_reason")
    op.drop_column("workflow_executions", "canceled_by_user_id")
