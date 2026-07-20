from __future__ import annotations

import pytest

from app.modules.modularity.contract import ModuleRegistry
from app.modules.modularity.registry import module_registry


def test_registry_loads_only_installed_modules() -> None:
    installed = module_registry.installed()

    assert [module.code for module in installed] == ["crm", "marketing", "projects", "support"]
    assert installed[0].version == "1.0.0"
    assert installed[0].migrations == ("20260716_0004",)
    assert "crm.contacts.view" in installed[0].permissions
    assert installed[1].migrations == ("20260720_0018",)
    assert "marketing.journeys.manage" in installed[1].permissions
    assert installed[2].migrations == ("20260720_0017",)
    assert "projects.tasks.manage" in installed[2].permissions
    assert installed[3].migrations == ("20260720_0016",)
    assert "support.tickets.view" in installed[3].permissions


def test_registry_rejects_duplicate_module_codes() -> None:
    registry = ModuleRegistry()
    definition = module_registry.installed()[0]
    registry.register(definition)

    with pytest.raises(ValueError, match="Módulo já registrado: crm"):
        registry.register(definition)
