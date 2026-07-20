"""Instala departamentos, colaboradores e afastamentos de RH.

Revision ID: 20260720_0021
Revises: 20260720_0020
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0021"
down_revision: str | None = "20260720_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = (
    ("hr.view", "hr", "view", "Visualizar recursos humanos"),
    ("hr.employees.manage", "hr", "employees.manage", "Gerenciar colaboradores"),
    ("hr.departments.manage", "hr", "departments.manage", "Gerenciar departamentos"),
    ("hr.leave.create", "hr", "leave.create", "Solicitar afastamentos"),
    ("hr.leave.decide", "hr", "leave.decide", "Decidir afastamentos"),
)


def _id() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
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
        sa.text("""
        INSERT INTO modules_catalog (code, name, description, version, category, is_core, status)
        VALUES ('hr', 'Recursos humanos', 'Gestao de pessoas e rotinas de RH.', '1.0.0', 'Gestao', false, 'installed')
        ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description,
            version = EXCLUDED.version, category = EXCLUDED.category, status = 'installed', updated_at = now()
    """)
    )
    op.execute(
        sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT roles.id, permissions.id FROM roles JOIN permissions ON permissions.module_code = 'hr'
        WHERE roles.is_system_role = true AND roles.name IN ('Proprietário', 'Proprietario') ON CONFLICT DO NOTHING
    """)
    )
    op.create_table(
        "hr_departments",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_hr_departments_company_name"),
        sa.UniqueConstraint("company_id", "code", name="uq_hr_departments_company_code"),
    )
    for column in ("company_id", "code", "name", "active"):
        op.create_index(f"ix_hr_departments_{column}", "hr_departments", [column])
    op.create_table(
        "hr_employees",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("manager_employee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("work_email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("position", sa.String(length=140), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("hire_date", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('active', 'on_leave', 'terminated')", name="ck_hr_employees_status"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["hr_departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["manager_employee_id"], ["hr_employees.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "employee_code", name="uq_hr_employees_company_code"),
        sa.UniqueConstraint("company_id", "work_email", name="uq_hr_employees_company_email"),
    )
    for column in (
        "company_id",
        "department_id",
        "manager_employee_id",
        "created_by_user_id",
        "employee_code",
        "name",
        "work_email",
        "position",
        "status",
        "hire_date",
        "termination_date",
        "created_at",
    ):
        op.create_index(f"ix_hr_employees_{column}", "hr_employees", [column])
    op.create_index("ix_hr_employees_company_status", "hr_employees", ["company_id", "status"])
    op.create_table(
        "hr_leave_requests",
        _id(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("leave_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("decision_note", sa.String(length=1000), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "leave_type IN ('vacation', 'sick', 'personal', 'other')",
            name="ck_hr_leave_requests_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_hr_leave_requests_status",
        ),
        sa.CheckConstraint("end_date >= start_date", name="ck_hr_leave_requests_dates"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["hr_employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "employee_id",
        "requested_by_user_id",
        "decided_by_user_id",
        "leave_type",
        "status",
        "start_date",
        "end_date",
        "created_at",
    ):
        op.create_index(f"ix_hr_leave_requests_{column}", "hr_leave_requests", [column])
    op.create_index(
        "ix_hr_leave_requests_company_status", "hr_leave_requests", ["company_id", "status"]
    )
    op.create_index(
        "ix_hr_leave_requests_company_period",
        "hr_leave_requests",
        ["company_id", "start_date", "end_date"],
    )


def downgrade() -> None:
    op.drop_table("hr_leave_requests")
    op.drop_table("hr_employees")
    op.drop_table("hr_departments")
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE module_code = 'hr')"
        )
    )
    op.execute(sa.text("DELETE FROM permissions WHERE module_code = 'hr'"))
    op.execute(
        sa.text(
            "UPDATE modules_catalog SET status = 'planned', updated_at = now() WHERE code = 'hr'"
        )
    )
