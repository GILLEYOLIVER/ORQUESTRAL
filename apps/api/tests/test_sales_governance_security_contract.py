from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_governance_routes_require_pipeline_permissions() -> None:
    source = (
        ROOT / "app/modules/crm/sales_governance_routes.py"
    ).read_text(encoding="utf-8")

    assert 'require_permission("crm.pipeline.view")' in source
    assert 'require_permission("crm.pipeline.manage")' in source
    assert "require_active_module" in source
    assert source.count("company_id=context.company_id") == 9


def test_governance_service_repeats_tenant_filters() -> None:
    source = (
        ROOT / "app/modules/crm/sales_governance_service.py"
    ).read_text(encoding="utf-8")

    assert source.count("company_id = :company_id") >= 18
    assert "account.company_id = :company_id" in source
    assert "opportunity.company_id = :company_id" in source
    assert "territory.company_id = :company_id" in source
    assert "created_by_user_id" in source


def test_governance_migration_forces_rls_and_is_reversible() -> None:
    source = (
        ROOT / "app/migrations/versions/20260723_0105_sales_governance.py"
    ).read_text(encoding="utf-8")

    assert "FORCE ROW LEVEL SECURITY" in source
    assert source.count("_rls(table)") == 1
    for table in (
        "crm_sales_territories",
        "crm_sales_goals",
        "crm_renewal_plans",
    ):
        assert table in source
        assert f'op.drop_table("{table}")' in source
