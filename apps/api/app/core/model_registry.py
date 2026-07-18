"""Importa os modelos para que o metadata do Alembic permaneça completo."""

from app.modules.agents.models import (
    Agent,
    AgentConversation,
    AgentMessage,
    AgentTool,
    AgentToolRun,
    AgentUsageRecord,
)
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
from app.modules.companies.models import Company
from app.modules.knowledge.models import KnowledgeBase, KnowledgeChunk, KnowledgeDocument
from app.modules.crm.models import CRMContact, CRMContactTag, CRMTag
from app.modules.modularity.models import CompanyModule, ModuleCatalog
from app.modules.plugins.models import CompanyPlugin, IntegrationCredential, Plugin, PluginConnectionTest
from app.modules.users.models import CompanyUser, User
from app.modules.workflows.models import Workflow, WorkflowExecution, WorkflowVersion

__all__ = [
    "Agent",
    "AgentConversation",
    "AgentMessage",
    "AgentTool",
    "AgentToolRun",
    "AgentUsageRecord",
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
    "ModuleCatalog",
    "PasswordResetToken",
    "Permission",
    "Plugin",
    "PluginConnectionTest",
    "Role",
    "RolePermission",
    "User",
    "Workflow",
    "WorkflowExecution",
    "WorkflowVersion",
]
