"""Adiciona papéis, permissões e auditoria de autorização.

Revision ID: 20260716_0003
Revises: 20260716_0002
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0003"
down_revision: str | None = "20260716_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMP = sa.DateTime(timezone=True)

PERMISSIONS = (
    ("platform.companies.view", "platform", "companies.view", "Visualizar empresas da plataforma"),
    (
        "platform.companies.create",
        "platform",
        "companies.create",
        "Cadastrar empresas na plataforma",
    ),
    ("platform.companies.update", "platform", "companies.update", "Alterar empresas da plataforma"),
    ("users.view", "users", "view", "Visualizar usuários da empresa"),
    ("users.create", "users", "create", "Convidar usuários para a empresa"),
    ("users.update", "users", "update", "Alterar usuários da empresa"),
    ("users.delete", "users", "delete", "Remover usuários da empresa"),
    ("roles.view", "roles", "view", "Visualizar papéis e permissões"),
    ("roles.create", "roles", "create", "Criar papéis personalizados"),
    ("roles.update", "roles", "update", "Alterar papéis personalizados"),
    ("roles.delete", "roles", "delete", "Excluir papéis personalizados"),
    ("agents.view", "agents", "view", "Visualizar agentes"),
    ("agents.create", "agents", "create", "Criar agentes"),
    ("agents.execute", "agents", "execute", "Executar agentes"),
    ("agents.configure", "agents", "configure", "Configurar agentes"),
    ("workflows.view", "workflows", "view", "Visualizar workflows"),
    ("workflows.execute", "workflows", "execute", "Executar workflows"),
    ("workflows.configure", "workflows", "configure", "Configurar workflows"),
    ("integrations.manage", "integrations", "manage", "Gerenciar integrações"),
    ("billing.view", "billing", "view", "Visualizar faturamento"),
    ("billing.manage", "billing", "manage", "Gerenciar faturamento"),
)


def _id() -> sa.Column[object]:
    return sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "permissions",
        _id(),
        sa.Column("code", sa.String(120), nullable=False),
        sa.Column("module_code", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"])
    op.create_index("ix_permissions_module_code", "permissions", ["module_code"])

    op.create_table(
        "roles",
        _id(),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("name", postgresql.CITEXT(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_system_role", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_roles_company_name"),
    )
    op.create_index("ix_roles_company_id", "roles", ["company_id"])
    op.create_index("ix_roles_name", "roles", ["name"])

    op.create_table(
        "role_permissions",
        sa.Column("role_id", UUID, nullable=False),
        sa.Column("permission_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])
    op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"])

    op.create_table(
        "authorization_audit_events",
        _id(),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("actor_user_id", UUID, nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(80), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_authorization_audit_events_company_id",
        "authorization_audit_events",
        ["company_id"],
    )
    op.create_index(
        "ix_authorization_audit_events_actor_user_id",
        "authorization_audit_events",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_authorization_audit_events_action", "authorization_audit_events", ["action"]
    )
    op.create_index(
        "ix_authorization_audit_events_created_at",
        "authorization_audit_events",
        ["created_at"],
    )

    op.create_foreign_key(
        "fk_company_users_role_id_roles",
        "company_users",
        "roles",
        ["role_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_company_users_role_id", "company_users", ["role_id"])

    permissions_table = sa.table(
        "permissions",
        sa.column("code", sa.String()),
        sa.column("module_code", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        permissions_table,
        [
            {
                "code": code,
                "module_code": module_code,
                "action": action,
                "description": description,
            }
            for code, module_code, action, description in PERMISSIONS
        ],
    )

    op.execute(
        """
        INSERT INTO roles (company_id, name, description, is_system_role)
        SELECT id, 'Proprietário', 'Acesso administrativo completo à empresa.', true
        FROM companies
        """
    )
    op.execute(
        """
        INSERT INTO roles (company_id, name, description, is_system_role)
        SELECT id, 'Membro', 'Acesso básico sem permissões administrativas.', true
        FROM companies
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT roles.id, permissions.id
        FROM roles
        CROSS JOIN permissions
        WHERE roles.name = 'Proprietário' AND permissions.module_code <> 'platform'
        """
    )
    op.execute(
        """
        UPDATE company_users AS membership
        SET role_id = roles.id
        FROM roles
        WHERE roles.company_id = membership.company_id
          AND roles.name = CASE WHEN membership.is_owner THEN 'Proprietário' ELSE 'Membro' END
        """
    )


def downgrade() -> None:
    op.drop_index("ix_company_users_role_id", table_name="company_users")
    op.drop_constraint("fk_company_users_role_id_roles", "company_users", type_="foreignkey")
    op.execute("UPDATE company_users SET role_id = NULL")
    op.drop_table("authorization_audit_events")
    op.drop_table("role_permissions")
    op.drop_table("roles")
    op.drop_table("permissions")
