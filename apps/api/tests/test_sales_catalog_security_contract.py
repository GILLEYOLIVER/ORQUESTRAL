from __future__ import annotations

from pathlib import Path

from app.modules.crm.sales_catalog_routes import router


def test_catalog_routes_have_module_and_permission_dependencies() -> None:
    names = {
        dependency.call.__name__
        for route in router.routes
        for dependency in route.dependant.dependencies
        if getattr(dependency.call, "__name__", None)
    }
    assert "module_dependency" in names
    assert "permission_dependency" in names
    assert len(router.routes) == 8


def test_catalog_service_scopes_business_queries_by_company() -> None:
    source = Path("app/modules/crm/sales_catalog_service.py").read_text()
    assert source.count("company_id = :company_id") >= 12
    assert "item.company_id = entry.company_id" in source
    assert "item.company_id = entry.company_id" in source
    assert '"email"' not in source
    assert '"phone"' not in source


def test_catalog_migration_forces_rls_on_every_new_table() -> None:
    source = Path(
        "app/migrations/versions/20260723_0104_sales_catalog_quotes.py"
    ).read_text()
    for table in (
        "crm_price_books",
        "crm_price_book_entries",
        "crm_quotes",
        "crm_quote_items",
    ):
        assert f'"{table}"' in source
    assert "FORCE ROW LEVEL SECURITY" in source
