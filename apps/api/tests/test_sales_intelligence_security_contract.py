from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sales_intelligence_routes_require_tenant_permission() -> None:
    source = (
        ROOT / "app/modules/crm/sales_intelligence_routes.py"
    ).read_text(encoding="utf-8")

    assert 'require_permission("crm.pipeline.view")' in source
    assert "require_active_module" in source
    assert source.count("company_id=context.company_id") == 2


def test_sales_intelligence_queries_keep_explicit_tenant_filters() -> None:
    source = (
        ROOT / "app/modules/crm/sales_intelligence_service.py"
    ).read_text(encoding="utf-8")

    assert "opportunity.company_id = :company_id" in source
    assert "stage.company_id = :company_id" in source
    assert "activity.company_id = :company_id" in source
    assert "quote.company_id = :company_id" in source
    assert "opportunity.deleted_at IS NULL" in source


def test_sales_intelligence_contract_does_not_return_sensitive_fields() -> None:
    source = (
        ROOT / "app/modules/crm/sales_intelligence_schemas.py"
    ).read_text(encoding="utf-8")

    for forbidden in ("email", "phone", "credential", "secret", "token"):
        assert forbidden not in source.lower()
