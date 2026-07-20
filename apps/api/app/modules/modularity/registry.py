from __future__ import annotations

from app.modules.analytics.manifest import analytics_module
from app.modules.crm.manifest import crm_module
from app.modules.finance.manifest import finance_module
from app.modules.hr.manifest import hr_module
from app.modules.inventory.manifest import inventory_module
from app.modules.marketing.manifest import marketing_module
from app.modules.modularity.contract import ModuleRegistry
from app.modules.projects.manifest import projects_module
from app.modules.support.manifest import support_module

module_registry = ModuleRegistry()
module_registry.register(analytics_module)
module_registry.register(crm_module)
module_registry.register(finance_module)
module_registry.register(hr_module)
module_registry.register(inventory_module)
module_registry.register(marketing_module)
module_registry.register(projects_module)
module_registry.register(support_module)
