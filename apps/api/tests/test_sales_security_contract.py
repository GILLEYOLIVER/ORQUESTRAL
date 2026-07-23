from __future__ import annotations

from pathlib import Path

from app.modules.crm.sales_routes import router


def test_sales_routes_require_explicit_permissions() -> None:
    dependencies = {
        dependency.call.__name__
        for route in router.routes
        for dependency in route.dependant.dependencies
        if getattr(dependency.call, "__name__", None)
    }
    assert "permission_dependency" in dependencies
    assert "module_dependency" in dependencies
    assert len(router.routes) == 7


def test_sales_service_scopes_every_root_query_by_company() -> None:
    source = Path("app/modules/crm/sales_service.py").read_text()
    assert source.count("CRMAccount.company_id == company_id") >= 4
    assert source.count("CRMLead.company_id == company_id") >= 4
    assert "CRMPipeline.company_id == company_id" in source
    assert "CRMPipelineStage.company_id == company_id" in source
    event_sections = source.split("DomainEventCreate(")[1:]
    assert event_sections
    assert all('"email"' not in section.split("),", 1)[0] for section in event_sections)
    assert all('"phone"' not in section.split("),", 1)[0] for section in event_sections)


def test_sales_migration_forces_rls() -> None:
    source = Path(
        "app/migrations/versions/20260723_0103_enterprise_sales_foundation.py"
    ).read_text()
    assert '_tenant_policy("crm_accounts")' in source
    assert '_tenant_policy("crm_leads")' in source
    assert "FORCE ROW LEVEL SECURITY" in source
