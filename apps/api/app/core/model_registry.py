"""Importa os modelos para que o metadata do Alembic permaneça completo."""

from app.modules.agents.models import (
    Agent,
    AgentConversation,
    AgentMessage,
    AgentTool,
    AgentToolRun,
    AgentUsageRecord,
)
from app.modules.audit.models import AuditEvent
from app.modules.authentication.models import (
    AuthAttempt,
    AuthSession,
    CompanyInvitation,
    PasswordResetToken,
)
from app.modules.authorization.models import (
    AuthorizationAuditEvent,
    Permission,
    Role,
    RolePermission,
)
from app.modules.billing.models import Plan, Subscription, UsageRecord
from app.modules.companies.models import Company
from app.modules.crm.models import CRMContact, CRMContactTag, CRMTag
from app.modules.knowledge.models import KnowledgeBase, KnowledgeChunk, KnowledgeDocument
from app.modules.metrics.models import MetricAggregationRun, MetricDailySummary
from app.modules.modularity.models import CompanyModule, ModuleCatalog
from app.modules.plugins.models import (
    CompanyPlugin,
    IntegrationCredential,
    Plugin,
    PluginConnectionTest,
)
from app.modules.users.models import CompanyUser, User
from app.modules.workflows.models import Workflow, WorkflowExecution, WorkflowVersion

__all__ = [
    "Agent",
    "AgentConversation",
    "AgentMessage",
    "AgentTool",
    "AgentToolRun",
    "AgentUsageRecord",
    "AuditEvent",
    "AuthAttempt",
    "AuthSession",
    "AuthorizationAuditEvent",
    "CRMContact",
    "CRMContactTag",
    "CRMTag",
    "Company",
    "CompanyInvitation",
    "CompanyModule",
    "CompanyPlugin",
    "CompanyUser",
    "IntegrationCredential",
    "KnowledgeBase",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "MetricAggregationRun",
    "MetricDailySummary",
    "ModuleCatalog",
    "PasswordResetToken",
    "Permission",
    "Plan",
    "Plugin",
    "PluginConnectionTest",
    "Role",
    "RolePermission",
    "Subscription",
    "UsageRecord",
    "User",
    "Workflow",
    "WorkflowExecution",
    "WorkflowVersion",
]
