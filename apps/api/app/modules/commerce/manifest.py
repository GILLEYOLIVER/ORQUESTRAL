from __future__ import annotations

from app.modules.commerce.routes import router
from app.modules.modularity.contract import ModuleDefinition, ModuleMenu

commerce_module = ModuleDefinition(
    code="commerce",
    name="Comércio e receita",
    version="1.0.0",
    permissions=(
        "commerce.view",
        "commerce.catalog.manage",
        "commerce.promotions.manage",
        "commerce.pricing.resolve",
    ),
    routers=(router,),
    menus=(
        ModuleMenu(
            label="Comércio e receita",
            path="/app/comercio",
            required_permission="commerce.view",
        ),
    ),
    configuration_schema={"type": "object", "properties": {}, "additionalProperties": False},
    events_published=(
        "commerce.variant.created",
        "commerce.promotion.activated",
    ),
    events_consumed=("inventory.item.updated", "crm.price_book.published"),
    migrations=("20260727_0115",),
)
