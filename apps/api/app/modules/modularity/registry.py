from __future__ import annotations

from app.modules.crm.manifest import crm_module
from app.modules.modularity.contract import ModuleRegistry

module_registry = ModuleRegistry()
module_registry.register(crm_module)
