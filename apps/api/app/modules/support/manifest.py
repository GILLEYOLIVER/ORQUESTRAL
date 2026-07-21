from __future__ import annotations

from app.modules.modularity.contract import ModuleDefinition, ModuleMenu
from app.modules.support.operations_routes import router as operations_router
from app.modules.support.routes import router

support_module = ModuleDefinition(
    code="support",
    name="Suporte",
    version="1.1.0",
    permissions=(
        "support.tickets.view",
        "support.tickets.create",
        "support.tickets.update",
        "support.tickets.comment",
    ),
    routers=(router, operations_router),
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
        "support.ticket.assigned",
        "support.ticket.sla_breached",
        "support.ticket.satisfaction_received",
    ),
    events_consumed=("crm.contact.updated",),
    migrations=("20260720_0016", "20260720_0026"),
)
