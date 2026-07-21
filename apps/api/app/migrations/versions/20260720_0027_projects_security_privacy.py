"""Deepen projects and enforce tenant-safe privacy deletion.

Revision ID: 20260720_0027
Revises: 20260720_0026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0027"
down_revision: str | None = "20260720_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_portfolios",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("objective", sa.String(length=500), nullable=True),
        sa.Column("budget_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("budget_cents >= 0", name="ck_project_portfolio_budget"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_project_portfolio_company_name"),
        sa.UniqueConstraint("company_id", "id", name="uq_project_portfolios_company_id_id"),
    )
    op.create_index("ix_project_portfolios_company_id", "project_portfolios", ["company_id"])

    op.add_column(
        "projects", sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "projects", sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "projects",
        sa.Column("health", sa.String(length=20), server_default="unknown", nullable=False),
    )
    op.add_column(
        "projects", sa.Column("budget_cents", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "projects", sa.Column("version", sa.Integer(), server_default="1", nullable=False)
    )
    op.create_foreign_key(
        "fk_projects_portfolio",
        "projects",
        "project_portfolios",
        ["portfolio_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_projects_owner", "projects", "users", ["owner_user_id"], ["id"], ondelete="SET NULL"
    )
    op.create_check_constraint(
        "ck_projects_health",
        "projects",
        "health IN ('unknown', 'on_track', 'at_risk', 'off_track')",
    )
    op.create_check_constraint("ck_projects_budget", "projects", "budget_cents >= 0")
    op.create_unique_constraint("uq_projects_company_id_id", "projects", ["company_id", "id"])
    for column in ("portfolio_id", "owner_user_id", "health"):
        op.create_index(f"ix_projects_{column}", "projects", [column])

    op.create_table(
        "project_milestones",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'at_risk', 'completed', 'cancelled')",
            name="ck_project_milestones_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["company_id", "project_id"],
            ["projects.company_id", "projects.id"],
            name="fk_project_milestones_tenant_project",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_project_milestone_project_name"),
        sa.UniqueConstraint("company_id", "id", name="uq_project_milestones_company_id_id"),
    )
    op.create_index("ix_project_milestones_company_id", "project_milestones", ["company_id"])
    op.create_index("ix_project_milestones_project_id", "project_milestones", ["project_id"])

    op.add_column(
        "project_tasks", sa.Column("milestone_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "project_tasks", sa.Column("assignee_user_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "project_tasks",
        sa.Column("estimated_minutes", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "project_tasks",
        sa.Column("actual_minutes", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "project_tasks", sa.Column("version", sa.Integer(), server_default="1", nullable=False)
    )
    op.create_foreign_key(
        "fk_project_tasks_milestone",
        "project_tasks",
        "project_milestones",
        ["milestone_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_project_tasks_assignee",
        "project_tasks",
        "users",
        ["assignee_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_project_tasks_effort", "project_tasks", "estimated_minutes >= 0 AND actual_minutes >= 0"
    )
    op.create_unique_constraint(
        "uq_project_tasks_company_id_id", "project_tasks", ["company_id", "id"]
    )
    op.create_foreign_key(
        "fk_project_tasks_tenant_project",
        "project_tasks",
        "projects",
        ["company_id", "project_id"],
        ["company_id", "id"],
        ondelete="CASCADE",
    )
    for column in ("milestone_id", "assignee_user_id"):
        op.create_index(f"ix_project_tasks_{column}", "project_tasks", [column])

    op.create_table(
        "project_risks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description_encrypted", sa.Text(), nullable=False),
        sa.Column("mitigation_encrypted", sa.Text(), nullable=True),
        sa.Column("probability", sa.Integer(), nullable=False),
        sa.Column("impact", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "probability >= 1 AND probability <= 5", name="ck_project_risk_probability"
        ),
        sa.CheckConstraint("impact >= 1 AND impact <= 5", name="ck_project_risk_impact"),
        sa.CheckConstraint(
            "status IN ('open', 'mitigating', 'accepted', 'closed')", name="ck_project_risk_status"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["company_id", "project_id"],
            ["projects.company_id", "projects.id"],
            name="fk_project_risks_tenant_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("company_id", "project_id", "owner_user_id"):
        op.create_index(f"ix_project_risks_{column}", "project_risks", [column])

    op.create_table(
        "project_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=120), server_default="Membro", nullable=False),
        sa.Column("allocation_percent", sa.Integer(), server_default="100", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "allocation_percent >= 1 AND allocation_percent <= 100",
            name="ck_project_member_allocation",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["company_id", "project_id"],
            ["projects.company_id", "projects.id"],
            name="fk_project_members_tenant_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_member_project_user"),
    )
    for column in ("company_id", "project_id", "user_id"):
        op.create_index(f"ix_project_members_{column}", "project_members", [column])

    op.create_table(
        "project_task_dependencies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("predecessor_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("successor_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "predecessor_task_id <> successor_task_id", name="ck_project_task_dependency_not_self"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["company_id", "project_id"],
            ["projects.company_id", "projects.id"],
            name="fk_project_dependencies_tenant_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "predecessor_task_id"],
            ["project_tasks.company_id", "project_tasks.id"],
            name="fk_project_dependencies_tenant_predecessor",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "successor_task_id"],
            ["project_tasks.company_id", "project_tasks.id"],
            name="fk_project_dependencies_tenant_successor",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "predecessor_task_id", "successor_task_id", name="uq_project_task_dependency_pair"
        ),
    )
    for column in ("company_id", "project_id", "predecessor_task_id", "successor_task_id"):
        op.create_index(
            f"ix_project_task_dependencies_{column}", "project_task_dependencies", [column]
        )

    op.drop_constraint("audit_events_company_id_fkey", "audit_events", type_="foreignkey")
    op.create_foreign_key(
        "audit_events_company_id_fkey",
        "audit_events",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("audit_events_company_id_fkey", "audit_events", type_="foreignkey")
    op.create_foreign_key(
        "audit_events_company_id_fkey",
        "audit_events",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_table("project_task_dependencies")
    op.drop_table("project_members")
    op.drop_table("project_risks")
    op.drop_constraint("fk_project_tasks_tenant_project", "project_tasks", type_="foreignkey")
    op.drop_constraint("uq_project_tasks_company_id_id", "project_tasks", type_="unique")
    op.drop_constraint("ck_project_tasks_effort", "project_tasks", type_="check")
    op.drop_constraint("fk_project_tasks_assignee", "project_tasks", type_="foreignkey")
    op.drop_constraint("fk_project_tasks_milestone", "project_tasks", type_="foreignkey")
    for column in ("assignee_user_id", "milestone_id"):
        op.drop_index(f"ix_project_tasks_{column}", table_name="project_tasks")
    for column in (
        "version",
        "actual_minutes",
        "estimated_minutes",
        "assignee_user_id",
        "milestone_id",
    ):
        op.drop_column("project_tasks", column)
    op.drop_table("project_milestones")
    op.drop_constraint("uq_projects_company_id_id", "projects", type_="unique")
    op.drop_constraint("ck_projects_budget", "projects", type_="check")
    op.drop_constraint("ck_projects_health", "projects", type_="check")
    op.drop_constraint("fk_projects_owner", "projects", type_="foreignkey")
    op.drop_constraint("fk_projects_portfolio", "projects", type_="foreignkey")
    for column in ("health", "owner_user_id", "portfolio_id"):
        op.drop_index(f"ix_projects_{column}", table_name="projects")
    for column in ("version", "budget_cents", "health", "owner_user_id", "portfolio_id"):
        op.drop_column("projects", column)
    op.drop_table("project_portfolios")
