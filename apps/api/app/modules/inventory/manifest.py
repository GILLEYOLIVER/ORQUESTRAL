from __future__ import annotations

from app.modules.inventory.routes import router
from app.modules.modularity.contract import ModuleDefinition, ModuleMenu

inventory_module = ModuleDefinition(
    code="inventory",
    name="Estoque",
    version="1.0.0",
    permissions=(
        "inventory.view",
        "inventory.items.manage",
        "inventory.movements.create",
        "inventory.locations.manage",
        "inventory.categories.manage",
    ),
    routers=(router,),
    menus=(
        ModuleMenu(
            label="Estoque",
            path="/app/estoque",
            required_permission="inventory.view",
        ),
    ),
    configuration_schema={"type": "object", "properties": {}, "additionalProperties": False},
    events_published=(
        "inventory.item.created",
        "inventory.item.updated",
        "inventory.movement.created",
        "inventory.low_stock.detected",
    ),
    events_consumed=(),
    migrations=("20260720_0019",),
)
