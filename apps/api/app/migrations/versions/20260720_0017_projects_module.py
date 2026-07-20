"""Instala o modulo de projetos e suas tarefas.

Revision ID: 20260720_0017
Revises: 20260720_0016
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0017"
down_revision: str | None = "20260720_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = (
    ("projects.view", "projects", "view", "Visualizar projetos"),
    ("projects.create", "projects", "create", "Criar projetos"),
    ("projects.update", "projects", "update", "Atualizar projetos"),
    ("projects.delete", "projects", "delete", "Arquivar projetos"),
    ("projects.tasks.manage", "projects", "tasks.manage", "Gerenciar tarefas de projetos"),
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
    op.execute(
        sa.text(
            """
            INSERT INTO modules_catalog
                (code, name, description, version, category, is_core, status)
            VALUES
                ('projects', 'Projetos', 'Planejamento e execucao de projetos.',
                 '1.0.0', 'Produtividade', false, 'installed')
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                version = EXCLUDED.version,
                category = EXCLUDED.category,
                status = 'installed',
                updated_at = now()
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT roles.id, permissions.id
              FROM roles
              JOIN permissions ON permissions.module_code = 'projects'
             WHERE roles.is_system_role = true
               AND roles.name IN ('Proprietário', 'Proprietario')
            ON CONFLICT DO NOTHING
            """
        )
    )
    op.create_table(
        "projects",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="planning", nullable=False),
        sa.Column("priority", sa.String(length=20), server_default="normal", nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('planning', 'active', 'on_hold', 'completed', 'cancelled')",
            name="ck_projects_status",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')", name="ck_projects_priority"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "created_by_user_id",
        "name",
        "status",
        "priority",
        "due_date",
        "archived_at",
        "created_at",
    ):
        op.create_index(f"ix_projects_{column}", "projects", [column])
    op.create_index("ix_projects_company_status", "projects", ["company_id", "status"])
    op.create_table(
        "project_tasks",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="todo", nullable=False),
        sa.Column("priority", sa.String(length=20), server_default="normal", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('todo', 'in_progress', 'blocked', 'done', 'cancelled')",
            name="ck_project_tasks_status",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')", name="ck_project_tasks_priority"
        ),
        sa.CheckConstraint("position >= 0", name="ck_project_tasks_position"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "project_id",
        "created_by_user_id",
        "title",
        "status",
        "priority",
        "due_date",
        "created_at",
    ):
        op.create_index(f"ix_project_tasks_{column}", "project_tasks", [column])
    op.create_index("ix_project_tasks_project_status", "project_tasks", ["project_id", "status"])


def downgrade() -> None:
    op.drop_table("project_tasks")
    op.drop_table("projects")
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE module_code = 'projects')"
        )
    )
    op.execute(sa.text("DELETE FROM permissions WHERE module_code = 'projects'"))
    op.execute(
        sa.text(
            "UPDATE modules_catalog SET status = 'planned', updated_at = now() WHERE code = 'projects'"
        )
    )
