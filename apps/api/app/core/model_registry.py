"""Importa os modelos para que o metadata do Alembic permaneça completo."""

from app.modules.agents.models import (
    Agent,
    AgentBudget,
    AgentConversation,
    AgentMessage,
    AgentRun,
    AgentTool,
    AgentToolRun,
    AgentUsageRecord,
    AgentVersion,
)
from app.modules.analytics.models import AnalyticsIndicator, AnalyticsMeasurement
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
from app.modules.crm.models import (
    CRMContact,
    CRMContactTag,
    CRMOpportunity,
    CRMOpportunityActivity,
    CRMPipeline,
    CRMPipelineStage,
    CRMTag,
)
from app.modules.finance.models import FinancialAccount, FinancialCategory, FinancialEntry
from app.modules.hr.models import HRDepartment, HREmployee, HRLeaveRequest
from app.modules.inventory.models import (
    InventoryBalance,
    InventoryCategory,
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
)
from app.modules.knowledge.models import KnowledgeBase, KnowledgeChunk, KnowledgeDocument
from app.modules.marketing.models import (
    MarketingAttribution,
    MarketingCampaign,
    MarketingCampaignContact,
    MarketingCampaignMetric,
    MarketingExperiment,
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
from app.modules.projects.models import (
    Project,
    ProjectMember,
    ProjectMilestone,
    ProjectPortfolio,
    ProjectRisk,
    ProjectTask,
    ProjectTaskDependency,
)
from app.modules.support.models import (
    SupportInteraction,
    SupportQueue,
    SupportSLAPolicy,
    SupportTicket,
    SupportTicketEvent,
)
from app.modules.users.models import CompanyUser, User
from app.modules.workflows.models import Workflow, WorkflowExecution, WorkflowVersion

__all__ = [
    "Agent",
    "AgentBudget",
    "AgentConversation",
    "AgentMessage",
    "AgentRun",
    "AgentTool",
    "AgentToolRun",
    "AgentUsageRecord",
    "AgentVersion",
    "AnalyticsIndicator",
    "AnalyticsMeasurement",
    "ApprovalAction",
    "ApprovalRequest",
    "AuditEvent",
    "AuthAttempt",
    "AuthSession",
    "AuthorizationAuditEvent",
    "CRMContact",
    "CRMContactTag",
    "CRMOpportunity",
    "CRMOpportunityActivity",
    "CRMPipeline",
    "CRMPipelineStage",
    "CRMTag",
    "Company",
    "CompanyInvitation",
    "CompanyModule",
    "CompanyPlugin",
    "CompanyUser",
    "FinancialAccount",
    "FinancialCategory",
    "FinancialEntry",
    "HRDepartment",
    "HREmployee",
    "HRLeaveRequest",
    "IntegrationCredential",
    "InventoryBalance",
    "InventoryCategory",
    "InventoryItem",
    "InventoryLocation",
    "InventoryMovement",
    "KnowledgeBase",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "MarketingAttribution",
    "MarketingCampaign",
    "MarketingCampaignContact",
    "MarketingCampaignMetric",
    "MarketingExperiment",
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
    "ProjectMember",
    "ProjectMilestone",
    "ProjectPortfolio",
    "ProjectRisk",
    "ProjectTask",
    "ProjectTaskDependency",
    "Role",
    "RolePermission",
    "Subscription",
    "SupportInteraction",
    "SupportQueue",
    "SupportSLAPolicy",
    "SupportTicket",
    "SupportTicketEvent",
    "UsageRecord",
    "User",
    "Workflow",
    "WorkflowExecution",
    "WorkflowVersion",
]

from app.modules.authorization import policy_models as _policy_models  # noqa: F401
from app.modules.events import models as _event_models  # noqa: F401
from app.modules.metadata import models as _metadata_models  # noqa: F401
