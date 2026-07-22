"""Add provider circuit state and remote cancellation capability status.

Revision ID: 20260722_0080
Revises: 20260722_0079
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260722_0080"
down_revision: str | None = "20260722_0079"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workflow_executions",
        sa.Column(
            "remote_cancel_status",
            sa.String(length=24),
            server_default="not_requested",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_workflow_executions_remote_cancel_status",
        "workflow_executions",
        "remote_cancel_status IN ('not_requested', 'unsupported', 'requested', 'confirmed', 'failed')",
    )
    op.create_table(
        "workflow_provider_circuits",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=20), server_default="closed", nullable=False),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_code", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "state IN ('closed', 'open', 'half_open')",
            name="ck_workflow_provider_circuit_state",
        ),
        sa.CheckConstraint("failure_count >= 0", name="ck_workflow_provider_circuit_failures"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "provider", name="uq_workflow_provider_circuit_company_provider"
        ),
    )
    op.create_index(
        "ix_workflow_provider_circuits_company_id",
        "workflow_provider_circuits",
        ["company_id"],
    )
    op.create_index(
        "ix_workflow_provider_circuits_retry_at", "workflow_provider_circuits", ["retry_at"]
    )


def downgrade() -> None:
    op.drop_table("workflow_provider_circuits")
    op.drop_constraint(
        "ck_workflow_executions_remote_cancel_status",
        "workflow_executions",
        type_="check",
    )
    op.drop_column("workflow_executions", "remote_cancel_status")
