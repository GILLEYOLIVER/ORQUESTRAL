from __future__ import annotations

from app.modules.crm.routes import router
from app.modules.modularity.contract import ModuleDefinition, ModuleMenu

crm_module = ModuleDefinition(
    code="crm",
    name="CRM",
    version="1.0.0",
    permissions=(
        "crm.contacts.view",
        "crm.contacts.create",
        "crm.contacts.update",
        "crm.contacts.delete",
    ),
    routers=(router,),
    menus=(
        ModuleMenu(
            label="Contatos",
            path="/app/crm/contatos",
            required_permission="crm.contacts.view",
        ),
    ),
    configuration_schema={"type": "object", "properties": {}, "additionalProperties": False},
    events_published=(
        "crm.contact.created",
        "crm.contact.updated",
        "crm.contact.deleted",
    ),
    migrations=("20260716_0004",),
)
