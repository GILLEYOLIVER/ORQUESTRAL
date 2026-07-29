"""governed developer sandboxes

Revision ID: 20260729_0122
Revises: 20260729_0121
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260729_0122"
down_revision: str | None = "20260729_0121"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
TABLES = ("developer_sandboxes", "artifact_promotions")


def _protect(table: str) -> None:
    op.create_index(f"ix_{table}_company_id", table, ["company_id"])
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')


def upgrade() -> None:
    op.create_table(
        "developer_sandboxes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("data_policy", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "environment IN ('development', 'testing', 'staging')",
            name="ck_developer_sandboxes_environment",
        ),
        sa.CheckConstraint(
            "data_policy IN ('empty', 'synthetic', 'masked')",
            name="ck_developer_sandboxes_data_policy",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')", name="ck_developer_sandboxes_status"
        ),
        sa.UniqueConstraint(
            "company_id", "code", name="uq_developer_sandboxes_company_code"
        ),
    )
    for column in ("created_by_user_id", "expires_at"):
        op.create_index(f"ix_developer_sandboxes_{column}", "developer_sandboxes", [column])
    _protect("developer_sandboxes")
    op.create_table(
        "artifact_promotions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(20), nullable=False),
        sa.Column("artifact_ref", sa.String(200), nullable=False),
        sa.Column("source_environment", sa.String(20), nullable=False),
        sa.Column("target_environment", sa.String(20), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), server_default="requested", nullable=False),
        sa.Column(
            "requested_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "reviewed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "artifact_type IN ('metadata', 'automation', 'agent', 'plugin')",
            name="ck_artifact_promotions_type",
        ),
        sa.CheckConstraint(
            "source_environment IN ('local', 'development', 'testing', 'staging')",
            name="ck_artifact_promotions_source",
        ),
        sa.CheckConstraint(
            "target_environment IN ('development', 'testing', 'staging', 'production')",
            name="ck_artifact_promotions_target",
        ),
        sa.CheckConstraint(
            "status IN ('requested', 'approved', 'rejected', 'applied', 'failed')",
            name="ck_artifact_promotions_status",
        ),
    )
    for column in ("requested_by_user_id", "reviewed_by_user_id", "requested_at"):
        op.create_index(f"ix_artifact_promotions_{column}", "artifact_promotions", [column])
    _protect("artifact_promotions")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
