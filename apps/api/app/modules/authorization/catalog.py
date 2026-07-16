from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PermissionDefinition:
    code: str
    module_code: str
    action: str
    description: str


PERMISSION_CATALOG = (
    PermissionDefinition(
        "platform.companies.view", "platform", "companies.view", "Visualizar empresas da plataforma"
    ),
    PermissionDefinition(
        "platform.companies.create",
        "platform",
        "companies.create",
        "Cadastrar empresas na plataforma",
    ),
    PermissionDefinition(
        "platform.companies.update",
        "platform",
        "companies.update",
        "Alterar empresas da plataforma",
    ),
    PermissionDefinition("users.view", "users", "view", "Visualizar usuários da empresa"),
    PermissionDefinition("users.create", "users", "create", "Convidar usuários para a empresa"),
    PermissionDefinition("users.update", "users", "update", "Alterar usuários da empresa"),
    PermissionDefinition("users.delete", "users", "delete", "Remover usuários da empresa"),
    PermissionDefinition("roles.view", "roles", "view", "Visualizar papéis e permissões"),
    PermissionDefinition("roles.create", "roles", "create", "Criar papéis personalizados"),
    PermissionDefinition("roles.update", "roles", "update", "Alterar papéis personalizados"),
    PermissionDefinition("roles.delete", "roles", "delete", "Excluir papéis personalizados"),
    PermissionDefinition("agents.view", "agents", "view", "Visualizar agentes"),
    PermissionDefinition("agents.create", "agents", "create", "Criar agentes"),
    PermissionDefinition("agents.execute", "agents", "execute", "Executar agentes"),
    PermissionDefinition("agents.configure", "agents", "configure", "Configurar agentes"),
    PermissionDefinition("workflows.view", "workflows", "view", "Visualizar workflows"),
    PermissionDefinition("workflows.execute", "workflows", "execute", "Executar workflows"),
    PermissionDefinition("workflows.configure", "workflows", "configure", "Configurar workflows"),
    PermissionDefinition("integrations.manage", "integrations", "manage", "Gerenciar integrações"),
    PermissionDefinition("billing.view", "billing", "view", "Visualizar faturamento"),
    PermissionDefinition("billing.manage", "billing", "manage", "Gerenciar faturamento"),
)

PLATFORM_PERMISSION_CODES = frozenset(
    definition.code for definition in PERMISSION_CATALOG if definition.module_code == "platform"
)
TENANT_PERMISSION_CODES = frozenset(
    definition.code for definition in PERMISSION_CATALOG if definition.module_code != "platform"
)

SYSTEM_OWNER_ROLE_NAME = "Proprietário"
SYSTEM_MEMBER_ROLE_NAME = "Membro"
