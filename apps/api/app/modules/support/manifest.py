from __future__ import annotations

from app.modules.modularity.contract import ModuleDefinition, ModuleMenu
from app.modules.support.channels_routes import ingress_router
from app.modules.support.channels_routes import router as channels_router
from app.modules.support.escalation_routes import router as escalation_router
from app.modules.support.operations_routes import router as operations_router
from app.modules.support.routes import router
from app.modules.support.routing_routes import router as routing_router

support_module = ModuleDefinition(
    code="support",
    name="Suporte",
    version="1.4.0",
    permissions=(
        "support.tickets.view",
        "support.tickets.create",
        "support.tickets.update",
        "support.tickets.comment",
    ),
    routers=(
        router,
        operations_router,
        routing_router,
        channels_router,
        ingress_router,
        escalation_router,
    ),
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
        "support.ticket.routed",
        "support.routing.configuration_updated",
        "support.channel.configuration_updated",
        "support.channel.message_received",
        "support.sla.configuration_updated",
        "support.sla.warning",
        "support.sla.escalated",
    ),
    events_consumed=("crm.contact.updated",),
    migrations=(
        "20260720_0016",
        "20260720_0026",
        "20260723_0106",
        "20260723_0107",
        "20260727_0108",
    ),
)
