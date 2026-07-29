"""analytics collaboration

Revision ID: 20260728_0119
Revises: 20260728_0118
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260728_0119"
down_revision: str | None = "20260728_0118"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
TABLES = (
    "analytics_collaboration_comments",
    "analytics_collaboration_mentions",
    "analytics_collaboration_followers",
)


def tenant() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
    ]


def protect(table: str) -> None:
    op.create_index(f"ix_{table}_company_id", table, ["company_id"])
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f"CREATE POLICY {table}_tenant_isolation ON {table} "
        "USING (company_id=NULLIF(current_setting('app.current_company_id',true),'')::uuid) "
        "WITH CHECK (company_id=NULLIF(current_setting('app.current_company_id',true),'')::uuid)"
    )


def upgrade() -> None:
    op.create_table(
        "analytics_collaboration_comments",
        *tenant(),
        sa.Column("resource_type", sa.String(20), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "parent_comment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analytics_collaboration_comments.id", ondelete="CASCADE"),
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "resource_type IN ('report','dashboard')",
            name="ck_analytics_collaboration_comments_resource",
        ),
    )
    op.create_index(
        "ix_analytics_collaboration_comments_resource",
        "analytics_collaboration_comments",
        ["company_id", "resource_type", "resource_id"],
    )
    op.create_table(
        "analytics_collaboration_mentions",
        *tenant(),
        sa.Column(
            "comment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analytics_collaboration_comments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mentioned_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "comment_id",
            "mentioned_user_id",
            name="uq_analytics_collaboration_mentions_comment_user",
        ),
    )
    op.create_table(
        "analytics_collaboration_followers",
        *tenant(),
        sa.Column("resource_type", sa.String(20), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "resource_type IN ('report','dashboard')",
            name="ck_analytics_collaboration_followers_resource",
        ),
        sa.UniqueConstraint(
            "company_id",
            "resource_type",
            "resource_id",
            "user_id",
            name="uq_analytics_collaboration_followers_resource_user",
        ),
    )
    for table in TABLES:
        protect(table)
    op.execute(
        "UPDATE modules_catalog SET version='2.1.0',updated_at=now() WHERE code='analytics'"
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute(
        "UPDATE modules_catalog SET version='2.0.0',updated_at=now() WHERE code='analytics'"
    )
