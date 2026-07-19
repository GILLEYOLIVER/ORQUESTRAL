from __future__ import annotations

from fastapi.testclient import TestClient


def test_notification_routes_require_authentication(client: TestClient) -> None:
    protected_routes = (
        "/notifications",
        "/notifications/summary",
        "/notifications/preferences",
        "/notifications/approvals",
    )

    for route in protected_routes:
        assert client.get(route).status_code == 401


def test_phase_13_routes_are_published_in_openapi(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    assert "/notifications" in paths
    assert "/notifications/summary" in paths
    assert "/notifications/preferences" in paths
    assert "/notifications/{notification_id}/read" in paths
    assert "/notifications/read-all" in paths
    assert "/notifications/approvals" in paths
    assert "/notifications/approvals/{approval_id}/comments" in paths
    assert "/notifications/approvals/{approval_id}/decision" in paths
