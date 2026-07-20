from __future__ import annotations

from app.modules.hr.routes import router
from app.modules.modularity.contract import ModuleDefinition, ModuleMenu

hr_module = ModuleDefinition(
    code="hr",
    name="Recursos humanos",
    version="1.0.0",
    permissions=(
        "hr.view",
        "hr.employees.manage",
        "hr.departments.manage",
        "hr.leave.create",
        "hr.leave.decide",
    ),
    routers=(router,),
    menus=(
        ModuleMenu(
            label="Recursos humanos",
            path="/app/recursos-humanos",
            required_permission="hr.view",
        ),
    ),
    configuration_schema={"type": "object", "properties": {}, "additionalProperties": False},
    events_published=(
        "hr.employee.created",
        "hr.employee.updated",
        "hr.leave.requested",
        "hr.leave.decided",
    ),
    events_consumed=(),
    migrations=("20260720_0021",),
)
