from __future__ import annotations

import pytest

from app.modules.authorization.catalog import TENANT_PERMISSION_CODES
from app.modules.modularity.contract import ModuleRegistry
from app.modules.modularity.registry import module_registry


def test_registry_loads_only_installed_modules() -> None:
    installed = module_registry.installed()

    assert [module.code for module in installed] == [
        "analytics",
        "commerce",
        "crm",
        "finance",
        "hr",
        "inventory",
        "marketing",
        "projects",
        "support",
    ]
    assert installed[0].version == "2.0.0"
    assert installed[0].migrations == ("20260720_0022", "20260728_0118")
    assert "analytics.measurements.manage" in installed[0].permissions
    assert installed[1].migrations == (
        "20260727_0115",
        "20260728_0116",
        "20260728_0117",
    )
    assert "commerce.pricing.resolve" in installed[1].permissions
    assert installed[2].migrations == (
        "20260716_0004",
        "20260720_0024",
        "20260723_0091",
        "20260723_0092",
        "20260723_0093",
        "20260723_0094",
        "20260723_0095",
        "20260723_0096",
        "20260723_0097",
        "20260723_0098",
        "20260723_0099",
        "20260723_0100",
        "20260723_0101",
        "20260723_0102",
        "20260723_0103",
        "20260723_0104",
        "20260723_0105",
    )
    assert "crm.contacts.view" in installed[2].permissions
    assert "crm.contacts.export" in installed[2].permissions
    assert "crm.segments.activate" in installed[2].permissions
    assert installed[3].migrations == ("20260720_0020",)
    assert "finance.entries.settle" in installed[3].permissions
    assert installed[4].migrations == ("20260720_0021",)
    assert "hr.leave.decide" in installed[4].permissions
    assert installed[5].migrations == ("20260720_0019",)
    assert "inventory.movements.create" in installed[5].permissions
    assert installed[6].migrations == (
        "20260720_0018",
        "20260720_0025",
        "20260727_0111",
        "20260727_0112",
        "20260727_0113",
        "20260727_0114",
    )
    assert "marketing.journeys.manage" in installed[6].permissions
    assert "marketing.agents.manage" in installed[6].permissions
    assert installed[7].migrations == ("20260720_0017", "20260720_0027")
    assert "projects.tasks.manage" in installed[7].permissions
    assert installed[8].migrations == (
        "20260720_0016",
        "20260720_0026",
        "20260723_0106",
        "20260723_0107",
        "20260727_0108",
        "20260727_0109",
        "20260727_0110",
    )
    assert "support.tickets.view" in installed[8].permissions
    for module in installed:
        assert set(module.permissions) <= TENANT_PERMISSION_CODES


def test_registry_rejects_duplicate_module_codes() -> None:
    registry = ModuleRegistry()
    definition = module_registry.installed()[0]
    registry.register(definition)

    with pytest.raises(ValueError, match="Módulo já registrado: analytics"):
        registry.register(definition)
