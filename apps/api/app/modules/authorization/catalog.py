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
    PermissionDefinition("modules.view", "modules", "view", "Visualizar módulos da empresa"),
    PermissionDefinition("modules.manage", "modules", "manage", "Ativar módulos da empresa"),
    PermissionDefinition("crm.contacts.view", "crm", "contacts.view", "Visualizar contatos do CRM"),
    PermissionDefinition("crm.contacts.create", "crm", "contacts.create", "Criar contatos no CRM"),
    PermissionDefinition(
        "crm.contacts.update", "crm", "contacts.update", "Alterar contatos no CRM"
    ),
    PermissionDefinition(
        "crm.contacts.delete", "crm", "contacts.delete", "Excluir contatos do CRM"
    ),
    PermissionDefinition(
        "support.tickets.view", "support", "tickets.view", "Visualizar chamados de suporte"
    ),
    PermissionDefinition(
        "support.tickets.create", "support", "tickets.create", "Criar chamados de suporte"
    ),
    PermissionDefinition(
        "support.tickets.update", "support", "tickets.update", "Atualizar chamados de suporte"
    ),
    PermissionDefinition(
        "support.tickets.comment",
        "support",
        "tickets.comment",
        "Registrar interacoes em chamados",
    ),
    PermissionDefinition("agents.view", "agents", "view", "Visualizar agentes"),
    PermissionDefinition("agents.create", "agents", "create", "Criar agentes"),
    PermissionDefinition("agents.execute", "agents", "execute", "Executar agentes"),
    PermissionDefinition("agents.configure", "agents", "configure", "Configurar agentes"),
    PermissionDefinition("knowledge.view", "knowledge", "view", "Visualizar bases de conhecimento"),
    PermissionDefinition("knowledge.manage", "knowledge", "manage", "Gerenciar bases e documentos"),
    PermissionDefinition("workflows.view", "workflows", "view", "Visualizar workflows"),
    PermissionDefinition("workflows.execute", "workflows", "execute", "Executar workflows"),
    PermissionDefinition("workflows.configure", "workflows", "configure", "Configurar workflows"),
    PermissionDefinition("metrics.view", "metrics", "view", "Visualizar dashboards e metricas"),
    PermissionDefinition("metrics.export", "metrics", "export", "Exportar relatorios gerenciais"),
    PermissionDefinition("audit.view", "audit", "view", "Consultar eventos de auditoria"),
    PermissionDefinition("integrations.manage", "integrations", "manage", "Gerenciar integrações"),
    PermissionDefinition("plugins.view", "plugins", "view", "Visualizar plugins da empresa"),
    PermissionDefinition(
        "plugins.manage", "plugins", "manage", "Ativar plugins e administrar credenciais"
    ),
    PermissionDefinition("billing.view", "billing", "view", "Visualizar faturamento"),
    PermissionDefinition("billing.manage", "billing", "manage", "Gerenciar faturamento"),
    PermissionDefinition("notifications.view", "notifications", "view", "Visualizar notificações"),
    PermissionDefinition(
        "notifications.manage", "notifications", "manage", "Administrar notificações"
    ),
    PermissionDefinition("approvals.view", "approvals", "view", "Visualizar aprovações"),
    PermissionDefinition("approvals.decide", "approvals", "decide", "Decidir aprovações"),
)

PLATFORM_PERMISSION_CODES = frozenset(
    definition.code for definition in PERMISSION_CATALOG if definition.module_code == "platform"
)
TENANT_PERMISSION_CODES = frozenset(
    definition.code for definition in PERMISSION_CATALOG if definition.module_code != "platform"
)

SYSTEM_OWNER_ROLE_NAME = "Proprietário"
SYSTEM_MEMBER_ROLE_NAME = "Membro"
