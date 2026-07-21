from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

MONITOR_SECRET = "development-only-change-me-agent-memory-monitor-secret-32"


def _monitor_headers(*, at: datetime | None = None, secret: str = MONITOR_SECRET) -> dict[str, str]:
    timestamp = str(int((at or datetime.now(UTC)).timestamp()))
    message = f"GET\n/health/agent-memory-scheduler\n{timestamp}"
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return {
        "X-Orkestral-Monitor-Timestamp": timestamp,
        "X-Orkestral-Monitor-Signature": signature,
    }


def test_health_returns_process_status(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == response.json()["request_id"]
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "Orkestral API"


def test_agent_memory_scheduler_health_is_generic(client: TestClient) -> None:
    assert client.get("/health/agent-memory-scheduler").status_code == 401
    assert (
        client.get(
            "/health/agent-memory-scheduler",
            headers=_monitor_headers(at=datetime.now(UTC) - timedelta(minutes=6)),
        ).status_code
        == 401
    )
    response = client.get("/health/agent-memory-scheduler", headers=_monitor_headers())

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["component"] == "agent-memory-worker"
    assert response.json()["state"] in {"idle", "healthy"}
    assert response.json()["monitor_secret_rotation_state"] == "not_configured"
    assert response.json()["monitor_secret_rotation_days_remaining"] is None
    assert response.json()["monitor_secret_rotation_policy"] == "optional"
    assert set(response.json()) == {
        "status",
        "component",
        "state",
        "monitor_secret_rotation_state",
        "monitor_secret_rotation_days_remaining",
        "monitor_secret_rotation_policy",
        "request_id",
    }

    client.app.state.settings.agent_memory_monitor_secret_rotated_at = datetime.now(
        UTC
    ) - timedelta(days=80)
    due_response = client.get("/health/agent-memory-scheduler", headers=_monitor_headers())
    assert due_response.status_code == 200
    assert due_response.json()["monitor_secret_rotation_state"] == "due_soon"
    assert 0 <= due_response.json()["monitor_secret_rotation_days_remaining"] <= 14

    previous_secret = "previous-monitor-secret-with-at-least-32-characters"
    client.app.state.settings.agent_memory_monitor_previous_secrets = [previous_secret]
    rotated_response = client.get(
        "/health/agent-memory-scheduler",
        headers=_monitor_headers(secret=previous_secret),
    )
    assert rotated_response.status_code == 200


def test_valid_request_id_is_propagated(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "external-request-123"})

    assert response.headers["X-Request-ID"] == "external-request-123"
    assert response.json()["request_id"] == "external-request-123"


def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "invalid id\n"})

    generated = response.headers["X-Request-ID"]
    assert generated != "invalid id\n"
    assert str(UUID(generated)) == generated
