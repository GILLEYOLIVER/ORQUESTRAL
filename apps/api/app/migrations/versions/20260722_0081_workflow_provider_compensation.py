"""Generalize workflow provider references and persist block compensation plans.

Revision ID: 20260722_0081
Revises: 20260722_0080
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260722_0081"
down_revision: str | None = "20260722_0080"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column("provider_key", sa.String(length=80), server_default="n8n", nullable=False),
    )
    op.add_column(
        "workflows", sa.Column("provider_workflow_id", sa.String(length=120), nullable=True)
    )
    op.add_column(
        "workflows", sa.Column("provider_version_id", sa.String(length=120), nullable=True)
    )
    op.execute(
        "UPDATE workflows SET provider_workflow_id = n8n_workflow_id, "
        "provider_version_id = n8n_version_id WHERE n8n_workflow_id IS NOT NULL"
    )
    op.create_index("ix_workflows_provider_key", "workflows", ["provider_key"])
    op.create_index("ix_workflows_provider_workflow_id", "workflows", ["provider_workflow_id"])
    op.create_unique_constraint(
        "uq_workflows_provider_reference",
        "workflows",
        ["provider_key", "provider_workflow_id"],
    )
    op.add_column(
        "workflow_executions",
        sa.Column("provider_key", sa.String(length=80), server_default="n8n", nullable=False),
    )
    op.add_column(
        "workflow_executions",
        sa.Column(
            "compensation_plan",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_index("ix_workflow_executions_provider_key", "workflow_executions", ["provider_key"])


def downgrade() -> None:
    op.drop_index("ix_workflow_executions_provider_key", table_name="workflow_executions")
    op.drop_column("workflow_executions", "compensation_plan")
    op.drop_column("workflow_executions", "provider_key")
    op.drop_constraint("uq_workflows_provider_reference", "workflows", type_="unique")
    op.drop_index("ix_workflows_provider_workflow_id", table_name="workflows")
    op.drop_index("ix_workflows_provider_key", table_name="workflows")
    op.drop_column("workflows", "provider_version_id")
    op.drop_column("workflows", "provider_workflow_id")
    op.drop_column("workflows", "provider_key")
