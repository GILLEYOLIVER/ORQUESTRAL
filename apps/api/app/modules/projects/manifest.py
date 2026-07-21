from __future__ import annotations

from app.modules.modularity.contract import ModuleDefinition, ModuleMenu
from app.modules.projects.portfolio_routes import router as portfolio_router
from app.modules.projects.routes import router

projects_module = ModuleDefinition(
    code="projects",
    name="Projetos",
    version="1.1.0",
    permissions=(
        "projects.view",
        "projects.create",
        "projects.update",
        "projects.delete",
        "projects.tasks.manage",
    ),
    routers=(router, portfolio_router),
    menus=(
        ModuleMenu(
            label="Projetos",
            path="/app/projetos",
            required_permission="projects.view",
        ),
    ),
    configuration_schema={"type": "object", "properties": {}, "additionalProperties": False},
    events_published=(
        "project.created",
        "project.updated",
        "project.task.created",
        "project.milestone.created",
        "project.risk.created",
        "project.governance.updated",
    ),
    events_consumed=(),
    migrations=("20260720_0017", "20260720_0027"),
)
