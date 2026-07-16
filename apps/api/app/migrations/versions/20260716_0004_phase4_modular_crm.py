"""Adiciona núcleo modular e CRM básico.

Revision ID: 20260716_0004
Revises: 20260716_0003
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0004"
down_revision: str | None = "20260716_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMP = sa.DateTime(timezone=True)

MODULE_PERMISSIONS = (
    ("modules.view", "modules", "view", "Visualizar módulos da empresa"),
    ("modules.manage", "modules", "manage", "Ativar módulos da empresa"),
    ("crm.contacts.view", "crm", "contacts.view", "Visualizar contatos do CRM"),
    ("crm.contacts.create", "crm", "contacts.create", "Criar contatos no CRM"),
    ("crm.contacts.update", "crm", "contacts.update", "Alterar contatos no CRM"),
    ("crm.contacts.delete", "crm", "contacts.delete", "Excluir contatos do CRM"),
)

MODULES = (
    (
        "crm",
        "CRM",
        "Gestão básica de contatos, etiquetas e responsáveis.",
        "1.0.0",
        "comercial",
        "installed",
        {"type": "object", "properties": {}, "additionalProperties": False},
    ),
    ("finance", "Financeiro", "Gestão financeira empresarial.", "0.0.0", "gestão", "planned", {}),
    (
        "support",
        "Suporte",
        "Atendimento e suporte ao cliente.",
        "0.0.0",
        "operações",
        "planned",
        {},
    ),
    (
        "human_resources",
        "Recursos humanos",
        "Gestão de pessoas e rotinas de RH.",
        "0.0.0",
        "gestão",
        "planned",
        {},
    ),
    (
        "inventory",
        "Estoque",
        "Controle de itens e movimentações.",
        "0.0.0",
        "operações",
        "planned",
        {},
    ),
    (
        "projects",
        "Projetos",
        "Planejamento e execução de projetos.",
        "0.0.0",
        "produtividade",
        "planned",
        {},
    ),
    (
        "marketing",
        "Marketing",
        "Campanhas e jornadas de marketing.",
        "0.0.0",
        "comercial",
        "planned",
        {},
    ),
    (
        "analytics",
        "Analytics",
        "Indicadores e análises consolidadas.",
        "0.0.0",
        "dados",
        "planned",
        {},
    ),
)


def _id() -> sa.Column[object]:
    return sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False)


def upgrade() -> None:
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
            for code, module_code, action, description in MODULE_PERMISSIONS
        ],
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT roles.id, permissions.id
        FROM roles
        CROSS JOIN permissions
        WHERE roles.name = 'Proprietário'
          AND permissions.code IN (
            'modules.view', 'modules.manage', 'crm.contacts.view',
            'crm.contacts.create', 'crm.contacts.update', 'crm.contacts.delete'
          )
        """
    )

    op.create_table(
        "modules_catalog",
        _id(),
        sa.Column("code", postgresql.CITEXT(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("is_core", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "configuration_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('installed', 'planned', 'disabled')",
            name="ck_modules_catalog_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_modules_catalog_code", "modules_catalog", ["code"])
    op.create_index("ix_modules_catalog_category", "modules_catalog", ["category"])
    op.create_index("ix_modules_catalog_status", "modules_catalog", ["status"])

    modules_table = sa.table(
        "modules_catalog",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("version", sa.String()),
        sa.column("category", sa.String()),
        sa.column("status", sa.String()),
        sa.column("configuration_schema", postgresql.JSONB()),
    )
    op.bulk_insert(
        modules_table,
        [
            {
                "code": code,
                "name": name,
                "description": description,
                "version": version,
                "category": category,
                "status": module_status,
                "configuration_schema": configuration_schema,
            }
            for (
                code,
                name,
                description,
                version,
                category,
                module_status,
                configuration_schema,
            ) in MODULES
        ],
        multiinsert=False,
    )

    op.create_table(
        "company_modules",
        _id(),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("module_id", UUID, nullable=False),
        sa.Column("status", sa.String(20), server_default="inactive", nullable=False),
        sa.Column(
            "configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("activated_at", TIMESTAMP, nullable=True),
        sa.Column("deactivated_at", TIMESTAMP, nullable=True),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_company_modules_status"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["module_id"], ["modules_catalog.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "module_id", name="uq_company_modules_company_module"),
    )
    op.create_index("ix_company_modules_company_id", "company_modules", ["company_id"])
    op.create_index("ix_company_modules_module_id", "company_modules", ["module_id"])

    op.create_table(
        "crm_contacts",
        _id(),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=True),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("company_name", sa.String(180), nullable=True),
        sa.Column("job_title", sa.String(120), nullable=True),
        sa.Column("source", sa.String(80), nullable=True),
        sa.Column("status", sa.String(20), server_default="lead", nullable=False),
        sa.Column("assigned_user_id", UUID, nullable=True),
        sa.Column("created_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", TIMESTAMP, nullable=True),
        sa.CheckConstraint(
            "status IN ('lead', 'prospect', 'customer', 'inactive')",
            name="ck_crm_contacts_status",
        ),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "name",
        "email",
        "company_name",
        "source",
        "status",
        "assigned_user_id",
        "created_at",
        "deleted_at",
    ):
        op.create_index(f"ix_crm_contacts_{column}", "crm_contacts", [column])

    op.create_table(
        "crm_tags",
        _id(),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("name", postgresql.CITEXT(), nullable=False),
        sa.Column("created_at", TIMESTAMP, server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_crm_tags_company_name"),
    )
    op.create_index("ix_crm_tags_company_id", "crm_tags", ["company_id"])
    op.create_index("ix_crm_tags_name", "crm_tags", ["name"])

    op.create_table(
        "crm_contact_tags",
        sa.Column("contact_id", UUID, nullable=False),
        sa.Column("tag_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["crm_contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["crm_tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("contact_id", "tag_id"),
    )
    op.create_index("ix_crm_contact_tags_contact_id", "crm_contact_tags", ["contact_id"])
    op.create_index("ix_crm_contact_tags_tag_id", "crm_contact_tags", ["tag_id"])


def downgrade() -> None:
    op.drop_table("crm_contact_tags")
    op.drop_table("crm_tags")
    op.drop_table("crm_contacts")
    op.drop_table("company_modules")
    op.drop_table("modules_catalog")
    op.execute(
        """
        DELETE FROM permissions
        WHERE code IN (
          'modules.view', 'modules.manage', 'crm.contacts.view',
          'crm.contacts.create', 'crm.contacts.update', 'crm.contacts.delete'
        )
        """
    )
