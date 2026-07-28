from __future__ import annotations

from app.modules.marketing.audience_routes import router as audience_router
from app.modules.marketing.growth_routes import router as growth_router
from app.modules.marketing.routes import router
from app.modules.modularity.contract import ModuleDefinition, ModuleMenu

marketing_module = ModuleDefinition(
    code="marketing",
    name="Marketing",
    version="1.2.0",
    permissions=(
        "marketing.view",
        "marketing.create",
        "marketing.update",
        "marketing.delete",
        "marketing.audience.manage",
        "marketing.journeys.manage",
    ),
    routers=(router, growth_router, audience_router),
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
    ),
    events_consumed=("crm.contact.updated",),
    migrations=("20260720_0018", "20260720_0025", "20260727_0111"),
)
