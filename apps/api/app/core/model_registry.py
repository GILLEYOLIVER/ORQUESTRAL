"""Importa os modelos para que o metadata do Alembic permaneça completo."""

from app.modules.agents.models import (
    Agent,
    AgentBudget,
    AgentConversation,
    AgentDataPolicy,
    AgentMessage,
    AgentRun,
    AgentSecurityEvent,
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
    ReadOnlyAccessLink,
)
from app.modules.authorization.models import (
    AuthorizationAuditEvent,
    Permission,
    Role,
    RolePermission,
)
from app.modules.billing.models import Plan, Subscription, UsageRecord
from app.modules.commerce.models import CommerceProductVariant, CommercePromotion
from app.modules.commerce.transaction_models import (
    CommerceContract,
    CommerceCustomerSubscription,
    CommerceInventoryReservation,
    CommerceOrder,
    CommerceOrderItem,
)
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
from app.modules.marketing.content_models import (
    MarketingChannelConnector,
    MarketingContent,
    MarketingContentVersion,
    MarketingFormSubmission,
    MarketingLandingPage,
    MarketingPublicPageRegistry,
)
from app.modules.marketing.governance_models import (
    MarketingContactPolicy,
    MarketingDeliveryAttempt,
)
from app.modules.marketing.lifecycle_models import (
    MarketingAgentRecommendation,
    MarketingExperimentEvidence,
    MarketingJourneySimulation,
    MarketingJourneyVersion,
)
from app.modules.marketing.models import (
    MarketingAttribution,
    MarketingAudience,
    MarketingAudienceMember,
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
from app.modules.support.agent_handoff_models import SupportAgentAssistRun, SupportHumanHandoff
from app.modules.support.engagement_models import (
    SupportResponseCitation,
    SupportResponseTemplate,
    SupportSatisfactionSurvey,
)
from app.modules.support.models import (
    SupportAgentCapacity,
    SupportAgentSkill,
    SupportBusinessCalendar,
    SupportChannelEndpoint,
    SupportChannelIngressEvent,
    SupportEscalationEvent,
    SupportEscalationPolicy,
    SupportInteraction,
    SupportQueue,
    SupportQueueSkill,
    SupportSkill,
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
    "AgentDataPolicy",
    "AgentMessage",
    "AgentRun",
    "AgentSecurityEvent",
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
    "CommerceContract",
    "CommerceCustomerSubscription",
    "CommerceInventoryReservation",
    "CommerceOrder",
    "CommerceOrderItem",
    "CommerceProductVariant",
    "CommercePromotion",
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
    "MarketingAgentRecommendation",
    "MarketingAttribution",
    "MarketingAudience",
    "MarketingAudienceMember",
    "MarketingCampaign",
    "MarketingCampaignContact",
    "MarketingCampaignMetric",
    "MarketingChannelConnector",
    "MarketingContactPolicy",
    "MarketingContent",
    "MarketingContentVersion",
    "MarketingDeliveryAttempt",
    "MarketingExperiment",
    "MarketingExperimentEvidence",
    "MarketingFormSubmission",
    "MarketingJourney",
    "MarketingJourneySimulation",
    "MarketingJourneyStep",
    "MarketingJourneyVersion",
    "MarketingLandingPage",
    "MarketingPublicPageRegistry",
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
    "ReadOnlyAccessLink",
    "Role",
    "RolePermission",
    "Subscription",
    "SupportAgentAssistRun",
    "SupportAgentCapacity",
    "SupportAgentSkill",
    "SupportBusinessCalendar",
    "SupportChannelEndpoint",
    "SupportChannelIngressEvent",
    "SupportEscalationEvent",
    "SupportEscalationPolicy",
    "SupportHumanHandoff",
    "SupportInteraction",
    "SupportQueue",
    "SupportQueueSkill",
    "SupportResponseCitation",
    "SupportResponseTemplate",
    "SupportSLAPolicy",
    "SupportSatisfactionSurvey",
    "SupportSkill",
    "SupportTicket",
    "SupportTicketEvent",
    "UsageRecord",
    "User",
    "Workflow",
    "WorkflowExecution",
    "WorkflowVersion",
]

from app.modules.agents import approval_policy_models as _agent_approval_policy_models  # noqa: F401
from app.modules.agents import coordination_models as _agent_coordination_models  # noqa: F401
from app.modules.agents import evaluation_models as _agent_evaluation_models  # noqa: F401
from app.modules.agents import memory_models as _agent_memory_models  # noqa: F401
from app.modules.agents import runtime_models as _agent_runtime_models  # noqa: F401
from app.modules.authorization import policy_models as _policy_models  # noqa: F401
from app.modules.events import models as _event_models  # noqa: F401
from app.modules.metadata import models as _metadata_models  # noqa: F401
from app.modules.support import agent_handoff_models as _support_agent_handoff_models  # noqa: F401
from app.modules.support import engagement_models as _support_engagement_models  # noqa: F401
