from __future__ import annotations

from app.modules.marketing.audience_routes import router as audience_router
from app.modules.marketing.content_routes import public_router
from app.modules.marketing.content_routes import router as content_router
from app.modules.marketing.governance_routes import router as governance_router
from app.modules.marketing.growth_routes import router as growth_router
from app.modules.marketing.lifecycle_routes import router as lifecycle_router
from app.modules.marketing.routes import router
from app.modules.modularity.contract import ModuleDefinition, ModuleMenu

marketing_module = ModuleDefinition(
    code="marketing",
    name="Marketing",
    version="1.5.0",
    permissions=(
        "marketing.view",
        "marketing.create",
        "marketing.update",
        "marketing.delete",
        "marketing.audience.manage",
        "marketing.journeys.manage",
        "marketing.governance.manage",
        "marketing.content.manage",
        "marketing.agents.manage",
    ),
    routers=(
        router,
        growth_router,
        audience_router,
        governance_router,
        content_router,
        lifecycle_router,
        public_router,
    ),
    menus=(
        ModuleMenu(
            label="Marketing",
            path="/app/marketing",
            required_permission="marketing.view",
        ),
    ),
    configuration_schema={"type": "object", "properties": {}, "additionalProperties": False},
    events_published=(
        "marketing.campaign.created",
        "marketing.campaign.updated",
        "marketing.journey.created",
        "marketing.metric.recorded",
        "marketing.experiment.created",
        "marketing.attribution.created",
        "marketing.audience.created",
        "marketing.audience.synchronized",
        "marketing.delivery.preflight",
        "marketing.content.created",
        "marketing.landing_page.published",
        "marketing.journey.published",
        "marketing.agent_recommendation.created",
    ),
    events_consumed=("crm.contact.updated",),
    migrations=(
        "20260720_0018",
        "20260720_0025",
        "20260727_0111",
        "20260727_0112",
        "20260727_0113",
        "20260727_0114",
    ),
)
