from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient


def test_health_returns_process_status(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == response.json()["request_id"]
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "Orkestral API"


def test_valid_request_id_is_propagated(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "external-request-123"})

    assert response.headers["X-Request-ID"] == "external-request-123"
    assert response.json()["request_id"] == "external-request-123"


def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "invalid id\n"})

    generated = response.headers["X-Request-ID"]
    assert generated != "invalid id\n"
    assert str(UUID(generated)) == generated
