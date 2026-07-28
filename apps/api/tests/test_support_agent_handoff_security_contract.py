from pathlib import Path


def test_handoff_routes_are_tenant_scoped_and_backend_authorized() -> None:
    source = Path("app/modules/support/agent_handoff_routes.py").read_text()
    assert source.count("== context.company_id") >= 7
    assert 'require_permission("agents.execute")' in source
    assert 'require_permission("support.tickets.update")' in source


def test_context_preserves_references_not_conversation_content() -> None:
    source = Path("app/modules/support/agent_handoff_service.py").read_text()
    assert 'select(SupportInteraction.id)' in source
    assert "SupportInteraction.message" not in source


def test_handoff_migration_forces_rls() -> None:
    source = Path(
        "app/migrations/versions/20260727_0110_support_agent_handoff.py"
    ).read_text()
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "prompt" not in source
    assert "secret" not in source
