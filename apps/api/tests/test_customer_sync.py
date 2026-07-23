from __future__ import annotations

from fastapi.testclient import TestClient

from app.modules.crm.customer_sync_service import retry_delay_seconds, secure_fingerprint


def test_sync_fingerprints_never_return_raw_cursor_or_lease() -> None:
    value = "cursor-client-sensitive-42"
    fingerprint = secure_fingerprint(value)
    assert fingerprint is not None
    assert len(fingerprint) == 64
    assert value not in fingerprint
    assert secure_fingerprint(None) is None


def test_sync_retry_backoff_is_exponential_and_capped() -> None:
    assert retry_delay_seconds(30, 1) == 30
    assert retry_delay_seconds(30, 2) == 60
    assert retry_delay_seconds(30, 5) == 480
    assert retry_delay_seconds(3_600, 20) == 86_400


def test_customer_sync_routes_are_protected_and_published(client: TestClient) -> None:
    assert client.get("/crm/customer-data/sync/connectors").status_code == 401
    assert client.get("/crm/customer-data/sync/runs").status_code == 401
    assert client.get("/crm/customer-data/sync/observability").status_code == 401
    paths = client.get("/openapi.json").json()["paths"]
    assert "/crm/customer-data/sync/connectors" in paths
    assert "/crm/customer-data/sync/connectors/{connector_id}/execute" in paths
    assert "/crm/customer-data/sync/connectors/{connector_id}/pause" in paths
    assert "/crm/customer-data/sync/connectors/{connector_id}/resume" in paths
    assert "/crm/customer-data/sync/runs" in paths
    assert "/crm/customer-data/sync/observability" in paths
