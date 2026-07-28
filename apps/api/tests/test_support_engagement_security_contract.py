from pathlib import Path


def test_engagement_service_scopes_business_queries_by_company() -> None:
    source = Path("app/modules/support/engagement_service.py").read_text()
    assert source.count("KnowledgeChunk.company_id == company_id") >= 2
    assert "SupportSatisfactionSurvey.company_id == company_id" in source


def test_engagement_routes_enforce_company_and_permissions() -> None:
    source = Path("app/modules/support/engagement_routes.py").read_text()
    assert source.count("== context.company_id") >= 4
    assert 'require_permission("support.tickets.comment")' in source
    assert 'require_permission("support.tickets.update")' in source


def test_engagement_migration_forces_rls_and_never_stores_comment() -> None:
    source = Path(
        "app/migrations/versions/20260727_0109_support_guided_responses.py"
    ).read_text()
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "comment_sha256" in source
    assert 'sa.Column("comment",' not in source
