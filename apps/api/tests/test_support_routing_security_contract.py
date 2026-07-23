from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_support_routing_tables_force_tenant_rls() -> None:
    migration = (
        ROOT / "app/migrations/versions/20260723_0106_support_skills_routing.py"
    ).read_text()
    for table in (
        "support_skills",
        "support_agent_capacities",
        "support_agent_skills",
        "support_queue_skills",
    ):
        assert f'"{table}"' in migration
        assert table in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "app.current_company_id" in migration


def test_support_routing_requires_backend_permissions_and_tenant_filters() -> None:
    routes = (ROOT / "app/modules/support/routing_routes.py").read_text()
    service = (ROOT / "app/modules/support/routing_service.py").read_text()

    assert 'require_permission("support.tickets.view")' in routes
    assert 'require_permission("support.tickets.update")' in routes
    assert "SupportTicket.company_id == company_id" in service
    assert "SupportAgentCapacity.company_id == company_id" in service
    assert "CompanyUser.company_id == company_id" in service
    assert "record_authorization_audit(" in service
    assert "enqueue_domain_event(" in service
    assert "ticket.description" not in service
    assert "ticket.message" not in service


def test_recommendation_and_assignment_are_separate_operations() -> None:
    routes = (ROOT / "app/modules/support/routing_routes.py").read_text()

    assert '"/tickets/{ticket_id}/recommend"' in routes
    assert '"/tickets/{ticket_id}/assign"' in routes
    assert "principal: CanViewTickets" in routes
    assert "principal: CanUpdateTickets" in routes
