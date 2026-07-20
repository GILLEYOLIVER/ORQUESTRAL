from __future__ import annotations

from app.modules.finance.routes import router
from app.modules.modularity.contract import ModuleDefinition, ModuleMenu

finance_module = ModuleDefinition(
    code="finance",
    name="Financeiro",
    version="1.0.0",
    permissions=(
        "finance.view",
        "finance.accounts.manage",
        "finance.entries.create",
        "finance.entries.update",
        "finance.entries.settle",
        "finance.categories.manage",
    ),
    routers=(router,),
    menus=(
        ModuleMenu(
            label="Financeiro",
            path="/app/financeiro",
            required_permission="finance.view",
        ),
    ),
    configuration_schema={"type": "object", "properties": {}, "additionalProperties": False},
    events_published=(
        "finance.entry.created",
        "finance.entry.settled",
        "finance.entry.overdue",
    ),
    events_consumed=(),
    migrations=("20260720_0020",),
)
