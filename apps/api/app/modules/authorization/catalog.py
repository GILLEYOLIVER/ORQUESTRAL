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
    PermissionDefinition(
        "access_links.manage",
        "users",
        "access_links.manage",
        "Gerar links seguros de acesso somente leitura",
    ),
    PermissionDefinition("portals.view", "portals", "view", "Visualizar portais da empresa"),
    PermissionDefinition(
        "portals.manage",
        "portals",
        "manage",
        "Configurar portais e convites externos da empresa",
    ),
    PermissionDefinition("roles.view", "roles", "view", "Visualizar papéis e permissões"),
    PermissionDefinition("roles.create", "roles", "create", "Criar papéis personalizados"),
    PermissionDefinition("roles.update", "roles", "update", "Alterar papéis personalizados"),
    PermissionDefinition("roles.delete", "roles", "delete", "Excluir papéis personalizados"),
    PermissionDefinition("modules.view", "modules", "view", "Visualizar módulos da empresa"),
    PermissionDefinition("modules.manage", "modules", "manage", "Ativar módulos da empresa"),
    PermissionDefinition("metadata.view", "metadata", "view", "Visualizar definicoes de metadados"),
    PermissionDefinition(
        "metadata.configure", "metadata", "configure", "Configurar definicoes de metadados"
    ),
    PermissionDefinition(
        "metadata.publish", "metadata", "publish", "Publicar definicoes de metadados"
    ),
    PermissionDefinition(
        "metadata.records.view", "metadata", "records.view", "Visualizar registros personalizados"
    ),
    PermissionDefinition(
        "metadata.records.create", "metadata", "records.create", "Criar registros personalizados"
    ),
    PermissionDefinition(
        "metadata.records.update", "metadata", "records.update", "Alterar registros personalizados"
    ),
    PermissionDefinition(
        "metadata.records.delete", "metadata", "records.delete", "Excluir registros personalizados"
    ),
    PermissionDefinition("crm.contacts.view", "crm", "contacts.view", "Visualizar contatos do CRM"),
    PermissionDefinition("crm.contacts.create", "crm", "contacts.create", "Criar contatos no CRM"),
    PermissionDefinition(
        "crm.contacts.update", "crm", "contacts.update", "Alterar contatos no CRM"
    ),
    PermissionDefinition(
        "crm.contacts.delete", "crm", "contacts.delete", "Excluir contatos do CRM"
    ),
    PermissionDefinition(
        "crm.contacts.export",
        "crm",
        "contacts.export",
        "Exportar dados pessoais governados do CRM",
    ),
    PermissionDefinition(
        "crm.segments.view",
        "crm",
        "segments.view",
        "Visualizar segmentos e busca de clientes",
    ),
    PermissionDefinition(
        "crm.segments.manage",
        "crm",
        "segments.manage",
        "Criar, materializar e publicar segmentos",
    ),
    PermissionDefinition(
        "crm.segments.activate",
        "crm",
        "segments.activate",
        "Ativar segmentos em destinos governados",
    ),
    PermissionDefinition(
        "crm.pipeline.view", "crm", "pipeline.view", "Visualizar funis comerciais"
    ),
    PermissionDefinition(
        "crm.pipeline.manage", "crm", "pipeline.manage", "Gerenciar funis comerciais"
    ),
    PermissionDefinition(
        "crm.opportunities.create", "crm", "opportunities.create", "Criar oportunidades"
    ),
    PermissionDefinition(
        "crm.opportunities.update", "crm", "opportunities.update", "Alterar oportunidades"
    ),
    PermissionDefinition(
        "crm.opportunities.delete", "crm", "opportunities.delete", "Excluir oportunidades"
    ),
    PermissionDefinition(
        "crm.activities.manage", "crm", "activities.manage", "Registrar atividades comerciais"
    ),
    PermissionDefinition(
        "crm.accounts.view", "crm", "accounts.view", "Visualizar contas empresariais"
    ),
    PermissionDefinition(
        "crm.accounts.manage", "crm", "accounts.manage", "Gerenciar contas empresariais"
    ),
    PermissionDefinition(
        "crm.leads.view", "crm", "leads.view", "Visualizar leads comerciais"
    ),
    PermissionDefinition(
        "crm.leads.manage", "crm", "leads.manage", "Gerenciar leads comerciais"
    ),
    PermissionDefinition(
        "crm.leads.qualify", "crm", "leads.qualify", "Qualificar leads comerciais"
    ),
    PermissionDefinition(
        "crm.leads.convert", "crm", "leads.convert", "Converter leads qualificados"
    ),
    PermissionDefinition(
        "crm.catalog.view", "crm", "catalog.view", "Visualizar catálogo e tabelas de preços"
    ),
    PermissionDefinition(
        "crm.catalog.manage", "crm", "catalog.manage", "Gerenciar tabelas de preços"
    ),
    PermissionDefinition(
        "crm.quotes.view", "crm", "quotes.view", "Visualizar propostas comerciais"
    ),
    PermissionDefinition(
        "crm.quotes.manage", "crm", "quotes.manage", "Criar e editar propostas comerciais"
    ),
    PermissionDefinition(
        "crm.quotes.publish", "crm", "quotes.publish", "Publicar e decidir propostas comerciais"
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
    PermissionDefinition("projects.view", "projects", "view", "Visualizar projetos"),
    PermissionDefinition("projects.create", "projects", "create", "Criar projetos"),
    PermissionDefinition("projects.update", "projects", "update", "Alterar projetos"),
    PermissionDefinition("projects.delete", "projects", "delete", "Excluir projetos"),
    PermissionDefinition(
        "projects.tasks.manage", "projects", "tasks.manage", "Gerenciar tarefas de projetos"
    ),
    PermissionDefinition("commerce.view", "commerce", "view", "Visualizar comércio e receita"),
    PermissionDefinition(
        "commerce.catalog.manage", "commerce", "catalog.manage", "Gerenciar variantes comerciais"
    ),
    PermissionDefinition(
        "commerce.promotions.manage", "commerce", "promotions.manage", "Gerenciar promoções"
    ),
    PermissionDefinition(
        "commerce.pricing.resolve", "commerce", "pricing.resolve", "Calcular preços e descontos"
    ),
    PermissionDefinition(
        "commerce.orders.manage", "commerce", "orders.manage", "Criar e reservar pedidos"
    ),
    PermissionDefinition(
        "commerce.orders.confirm",
        "commerce",
        "orders.confirm",
        "Confirmar pedidos e gerar efeitos financeiros",
    ),
    PermissionDefinition(
        "commerce.contracts.view", "commerce", "contracts.view", "Visualizar contratos comerciais"
    ),
    PermissionDefinition("marketing.view", "marketing", "view", "Visualizar marketing"),
    PermissionDefinition("marketing.create", "marketing", "create", "Criar campanhas"),
    PermissionDefinition("marketing.update", "marketing", "update", "Alterar campanhas"),
    PermissionDefinition("marketing.delete", "marketing", "delete", "Excluir campanhas"),
    PermissionDefinition(
        "marketing.audience.manage",
        "marketing",
        "audience.manage",
        "Gerenciar publicos de campanhas",
    ),
    PermissionDefinition(
        "marketing.journeys.manage",
        "marketing",
        "journeys.manage",
        "Gerenciar jornadas de marketing",
    ),
    PermissionDefinition(
        "marketing.governance.manage",
        "marketing",
        "governance.manage",
        "Gerenciar consentimento, frequência e horários de contato",
    ),
    PermissionDefinition(
        "marketing.content.manage",
        "marketing",
        "content.manage",
        "Gerenciar canais, conteúdos, páginas e formulários",
    ),
    PermissionDefinition(
        "marketing.agents.manage",
        "marketing",
        "agents.manage",
        "Gerenciar recomendações de agentes de marketing",
    ),
    PermissionDefinition("inventory.view", "inventory", "view", "Visualizar estoque"),
    PermissionDefinition(
        "inventory.items.manage", "inventory", "items.manage", "Gerenciar itens de estoque"
    ),
    PermissionDefinition(
        "inventory.movements.create",
        "inventory",
        "movements.create",
        "Registrar movimentacoes de estoque",
    ),
    PermissionDefinition(
        "inventory.locations.manage",
        "inventory",
        "locations.manage",
        "Gerenciar locais de estoque",
    ),
    PermissionDefinition(
        "inventory.categories.manage",
        "inventory",
        "categories.manage",
        "Gerenciar categorias de estoque",
    ),
    PermissionDefinition("finance.view", "finance", "view", "Visualizar financeiro"),
    PermissionDefinition(
        "finance.accounts.manage", "finance", "accounts.manage", "Gerenciar contas financeiras"
    ),
    PermissionDefinition(
        "finance.entries.create", "finance", "entries.create", "Criar lancamentos financeiros"
    ),
    PermissionDefinition(
        "finance.entries.update", "finance", "entries.update", "Alterar lancamentos financeiros"
    ),
    PermissionDefinition(
        "finance.entries.settle", "finance", "entries.settle", "Liquidar lancamentos financeiros"
    ),
    PermissionDefinition(
        "finance.categories.manage",
        "finance",
        "categories.manage",
        "Gerenciar categorias financeiras",
    ),
    PermissionDefinition("hr.view", "hr", "view", "Visualizar recursos humanos"),
    PermissionDefinition(
        "hr.employees.manage", "hr", "employees.manage", "Gerenciar colaboradores"
    ),
    PermissionDefinition(
        "hr.departments.manage", "hr", "departments.manage", "Gerenciar departamentos"
    ),
    PermissionDefinition("hr.leave.create", "hr", "leave.create", "Solicitar afastamentos"),
    PermissionDefinition("hr.leave.decide", "hr", "leave.decide", "Decidir afastamentos"),
    PermissionDefinition("analytics.view", "analytics", "view", "Visualizar Analytics"),
    PermissionDefinition(
        "analytics.indicators.manage",
        "analytics",
        "indicators.manage",
        "Gerenciar indicadores e metas",
    ),
    PermissionDefinition(
        "analytics.measurements.manage",
        "analytics",
        "measurements.manage",
        "Registrar medicoes de indicadores",
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
    PermissionDefinition("events.view", "events", "view", "Visualizar eventos empresariais"),
    PermissionDefinition(
        "events.configure", "events", "configure", "Configurar contratos e assinaturas"
    ),
    PermissionDefinition("events.replay", "events", "replay", "Reprocessar eventos com falha"),
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
