from __future__ import annotations

from app.modules.commerce.routes import router
from app.modules.commerce.transaction_routes import router as transaction_router
from app.modules.modularity.contract import ModuleDefinition, ModuleMenu

commerce_module = ModuleDefinition(
    code="commerce",
    name="Comércio e receita",
    version="1.1.0",
    permissions=(
        "commerce.view",
        "commerce.catalog.manage",
        "commerce.promotions.manage",
        "commerce.pricing.resolve",
        "commerce.orders.manage",
        "commerce.orders.confirm",
        "commerce.contracts.view",
    ),
    routers=(router, transaction_router),
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
        "commerce.order.created",
        "commerce.order.confirmed",
        "commerce.order.cancelled",
        "commerce.order.fulfilled",
    ),
    events_consumed=("inventory.item.updated", "crm.price_book.published"),
    migrations=("20260727_0115", "20260728_0116"),
)
