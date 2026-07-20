"""Sincroniza catalogo, versoes e permissoes dos modulos empresariais.

Revision ID: 20260720_0023
Revises: 20260720_0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0023"
down_revision: str | None = "20260720_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PERMISSIONS = (
    ("projects.view", "projects", "view", "Visualizar projetos"),
    ("projects.create", "projects", "create", "Criar projetos"),
    ("projects.update", "projects", "update", "Alterar projetos"),
    ("projects.delete", "projects", "delete", "Excluir projetos"),
    ("projects.tasks.manage", "projects", "tasks.manage", "Gerenciar tarefas de projetos"),
    ("marketing.view", "marketing", "view", "Visualizar marketing"),
    ("marketing.create", "marketing", "create", "Criar campanhas"),
    ("marketing.update", "marketing", "update", "Alterar campanhas"),
    ("marketing.delete", "marketing", "delete", "Excluir campanhas"),
    (
        "marketing.audience.manage",
        "marketing",
        "audience.manage",
        "Gerenciar publicos de campanhas",
    ),
    (
        "marketing.journeys.manage",
        "marketing",
        "journeys.manage",
        "Gerenciar jornadas de marketing",
    ),
    ("inventory.view", "inventory", "view", "Visualizar estoque"),
    ("inventory.items.manage", "inventory", "items.manage", "Gerenciar itens de estoque"),
    (
        "inventory.movements.create",
        "inventory",
        "movements.create",
        "Registrar movimentacoes de estoque",
    ),
    (
        "inventory.locations.manage",
        "inventory",
        "locations.manage",
        "Gerenciar locais de estoque",
    ),
    (
        "inventory.categories.manage",
        "inventory",
        "categories.manage",
        "Gerenciar categorias de estoque",
    ),
    ("finance.view", "finance", "view", "Visualizar financeiro"),
    ("finance.accounts.manage", "finance", "accounts.manage", "Gerenciar contas financeiras"),
    ("finance.entries.create", "finance", "entries.create", "Criar lancamentos financeiros"),
    ("finance.entries.update", "finance", "entries.update", "Alterar lancamentos financeiros"),
    ("finance.entries.settle", "finance", "entries.settle", "Liquidar lancamentos financeiros"),
    (
        "finance.categories.manage",
        "finance",
        "categories.manage",
        "Gerenciar categorias financeiras",
    ),
    ("hr.view", "hr", "view", "Visualizar recursos humanos"),
    ("hr.employees.manage", "hr", "employees.manage", "Gerenciar colaboradores"),
    ("hr.departments.manage", "hr", "departments.manage", "Gerenciar departamentos"),
    ("hr.leave.create", "hr", "leave.create", "Solicitar afastamentos"),
    ("hr.leave.decide", "hr", "leave.decide", "Decidir afastamentos"),
    ("analytics.view", "analytics", "view", "Visualizar Analytics"),
    (
        "analytics.indicators.manage",
        "analytics",
        "indicators.manage",
        "Gerenciar indicadores e metas",
    ),
    (
        "analytics.measurements.manage",
        "analytics",
        "measurements.manage",
        "Registrar medicoes de indicadores",
    ),
)


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            legacy_id uuid;
            canonical_id uuid;
        BEGIN
            SELECT id INTO legacy_id FROM modules_catalog WHERE code = 'human_resources';
            SELECT id INTO canonical_id FROM modules_catalog WHERE code = 'hr';
            IF legacy_id IS NOT NULL AND canonical_id IS NULL THEN
                UPDATE modules_catalog SET code = 'hr' WHERE id = legacy_id;
            ELSIF legacy_id IS NOT NULL AND canonical_id IS NOT NULL THEN
                UPDATE company_modules source
                SET module_id = canonical_id
                WHERE source.module_id = legacy_id
                  AND NOT EXISTS (
                    SELECT 1 FROM company_modules target
                    WHERE target.company_id = source.company_id
                      AND target.module_id = canonical_id
                  );
                DELETE FROM company_modules WHERE module_id = legacy_id;
                DELETE FROM modules_catalog WHERE id = legacy_id;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        UPDATE modules_catalog
        SET status = 'installed', version = '1.0.0', updated_at = now()
        WHERE code IN ('support', 'projects', 'marketing', 'inventory', 'finance', 'hr', 'analytics');
        """
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
        INSERT INTO permissions (code, module_code, action, description)
        VALUES (:code, :module_code, :action, :description)
        ON CONFLICT (code) DO UPDATE SET
            module_code = EXCLUDED.module_code,
            action = EXCLUDED.action,
            description = EXCLUDED.description;
        """
        ),
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
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT roles.id, permissions.id
        FROM roles
        CROSS JOIN permissions
        WHERE roles.is_system_role = true
          AND lower(roles.name) = lower('Proprietário')
          AND permissions.module_code IN (
              'projects', 'marketing', 'inventory', 'finance', 'hr', 'analytics'
          )
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM permissions
        WHERE code IN (
            'analytics.view',
            'analytics.indicators.manage',
            'analytics.measurements.manage'
        );
        """
    )
    op.execute(
        """
        UPDATE modules_catalog
        SET status = 'planned', version = '0.0.0', updated_at = now()
        WHERE code IN ('support', 'projects', 'marketing', 'inventory', 'finance', 'hr', 'analytics');
        """
    )
    op.execute(
        """
        UPDATE modules_catalog
        SET code = 'human_resources'
        WHERE code = 'hr'
          AND NOT EXISTS (SELECT 1 FROM modules_catalog WHERE code = 'human_resources');
        """
    )
