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
from app.modules.inventory.models import (
    InventoryBalance,
    InventoryCategory,
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
)
from app.modules.knowledge.models import KnowledgeBase, KnowledgeChunk, KnowledgeDocument
from app.modules.marketing.models import (
    MarketingCampaign,
    MarketingCampaignContact,
    MarketingJourney,
    MarketingJourneyStep,
)
from app.modules.metrics.models import MetricAggregationRun, MetricDailySummary
from app.modules.modularity.models import CompanyModule, ModuleCatalog
from app.modules.notifications.models import (
    ApprovalAction,
    ApprovalRequest,
    Notification,
    NotificationPreference,
)
from app.modules.plugins.models import (
    CompanyPlugin,
    IntegrationCredential,
    Plugin,
    PluginConnectionTest,
)
from app.modules.projects.models import Project, ProjectTask
from app.modules.support.models import SupportInteraction, SupportTicket
from app.modules.users.models import CompanyUser, User
from app.modules.workflows.models import Workflow, WorkflowExecution, WorkflowVersion

__all__ = [
    "Agent",
    "AgentConversation",
    "AgentMessage",
    "AgentTool",
    "AgentToolRun",
    "AgentUsageRecord",
    "ApprovalAction",
    "ApprovalRequest",
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
    "InventoryBalance",
    "InventoryCategory",
    "InventoryItem",
    "InventoryLocation",
    "InventoryMovement",
    "KnowledgeBase",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "MarketingCampaign",
    "MarketingCampaignContact",
    "MarketingJourney",
    "MarketingJourneyStep",
    "MetricAggregationRun",
    "MetricDailySummary",
    "ModuleCatalog",
    "Notification",
    "NotificationPreference",
    "PasswordResetToken",
    "Permission",
    "Plan",
    "Plugin",
    "PluginConnectionTest",
    "Project",
    "ProjectTask",
    "Role",
    "RolePermission",
    "Subscription",
    "SupportInteraction",
    "SupportTicket",
    "UsageRecord",
    "User",
    "Workflow",
    "WorkflowExecution",
    "WorkflowVersion",
]
