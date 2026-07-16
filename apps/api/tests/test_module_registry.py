from __future__ import annotations

import pytest

from app.modules.modularity.contract import ModuleRegistry
from app.modules.modularity.registry import module_registry


def test_registry_loads_only_installed_modules() -> None:
    installed = module_registry.installed()

    assert [module.code for module in installed] == ["crm"]
    assert installed[0].version == "1.0.0"
    assert installed[0].migrations == ("20260716_0004",)
    assert "crm.contacts.view" in installed[0].permissions


def test_registry_rejects_duplicate_module_codes() -> None:
    registry = ModuleRegistry()
    definition = module_registry.installed()[0]
    registry.register(definition)

    with pytest.raises(ValueError, match="Módulo já registrado: crm"):
        registry.register(definition)
