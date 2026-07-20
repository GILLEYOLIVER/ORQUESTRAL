from __future__ import annotations

from app.modules.marketing.routes import router
from app.modules.modularity.contract import ModuleDefinition, ModuleMenu

marketing_module = ModuleDefinition(
    code="marketing",
    name="Marketing",
    version="1.0.0",
    permissions=(
        "marketing.view",
        "marketing.create",
        "marketing.update",
        "marketing.delete",
        "marketing.audience.manage",
        "marketing.journeys.manage",
    ),
    routers=(router,),
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
    ),
    events_consumed=("crm.contact.updated",),
    migrations=("20260720_0018",),
)
