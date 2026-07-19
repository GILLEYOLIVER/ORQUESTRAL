"""Construtor visual e historico de versoes.

Revision ID: 20260718_0010
Revises: 20260718_0009
Create Date: 2026-07-18
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260718_0010"
down_revision: str | None = "20260718_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMP = sa.DateTime(timezone=True)
DEFAULT_DEFINITION = {
    "nodes": [
        {
            "id": "trigger-manual",
            "type": "trigger.manual",
            "label": "Inicio manual",
            "position": {"x": 80, "y": 180},
            "config": {},
        },
        {
            "id": "flow-end",
            "type": "flow.end",
            "label": "Encerramento",
            "position": {"x": 430, "y": 180},
            "config": {},
        },
    ],
    "connections": [
        {
            "id": "edge-trigger-end",
            "source": "trigger-manual",
            "target": "flow-end",
            "source_handle": "main",
        }
    ],
    "variables": {},
    "version": 1,
}


def upgrade() -> None:
    op.create_table(
        "workflow_versions",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("workflow_id", UUID, nullable=False),
        sa.Column("created_by_user_id", UUID, nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("change_summary", sa.String(500), nullable=True),
        sa.Column("created_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_workflow_versions_version"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "version", name="uq_workflow_versions_workflow_version"),
    )
    for column in ("company_id", "workflow_id", "created_by_user_id", "created_at"):
        op.create_index(f"ix_workflow_versions_{column}", "workflow_versions", [column])

    connection = op.get_bind()
    neutral = json.dumps(DEFAULT_DEFINITION)
    connection.execute(
        sa.text(
            "UPDATE workflows SET definition=CAST(:definition AS jsonb), sync_status='pending'"
        ),
        {"definition": neutral},
    )
    connection.execute(
        sa.text("""
        INSERT INTO workflow_versions (
            company_id, workflow_id, created_by_user_id, version, name,
            description, definition, change_summary
        )
        SELECT company_id, id, created_by_user_id, version, name,
               description, definition, 'Migrada para o construtor visual'
        FROM workflows
    """)
    )


def downgrade() -> None:
    op.drop_table("workflow_versions")
