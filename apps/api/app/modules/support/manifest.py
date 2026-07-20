from __future__ import annotations

from app.modules.modularity.contract import ModuleDefinition, ModuleMenu
from app.modules.support.routes import router

support_module = ModuleDefinition(
    code="support",
    name="Suporte",
    version="1.0.0",
    permissions=(
        "support.tickets.view",
        "support.tickets.create",
        "support.tickets.update",
        "support.tickets.comment",
    ),
    routers=(router,),
    menus=(
        ModuleMenu(
            label="Suporte",
            path="/app/suporte",
            required_permission="support.tickets.view",
        ),
    ),
    configuration_schema={"type": "object", "properties": {}, "additionalProperties": False},
    events_published=(
        "support.ticket.created",
        "support.ticket.updated",
        "support.interaction.created",
    ),
    events_consumed=("crm.contact.updated",),
    migrations=("20260720_0016",),
)
