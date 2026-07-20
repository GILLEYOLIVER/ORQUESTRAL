from app.modules.analytics.routes import router
from app.modules.modularity.contract import ModuleDefinition, ModuleMenu

analytics_module = ModuleDefinition(
    code="analytics",
    name="Analytics",
    version="1.0.0",
    permissions=(
        "analytics.view",
        "analytics.indicators.manage",
        "analytics.measurements.manage",
    ),
    routers=(router,),
    menus=(
        ModuleMenu(
            label="Analytics",
            path="/app/analytics",
            required_permission="analytics.view",
        ),
    ),
    events_published=("analytics.indicator.created", "analytics.measurement.recorded"),
    migrations=("20260720_0022",),
)
