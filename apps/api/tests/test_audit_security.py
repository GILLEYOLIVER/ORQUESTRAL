from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.redaction import REDACTED, redact_sensitive_data, redact_structlog_event
from app.core.security import create_access_token, decode_access_token
from app.main import create_app


def test_redaction_removes_nested_credentials_without_hiding_usage_metrics() -> None:
    payload = {
        "password": "Segredo-2026!",
        "nested": {"access_token": "token-real", "token_count": 42},
        "credentials": [{"api_key": "chave-real"}],
    }

    redacted = redact_sensitive_data(payload)

    assert redacted["password"] == REDACTED
    assert redacted["nested"]["access_token"] == REDACTED
    assert redacted["nested"]["token_count"] == 42
    assert redacted["credentials"] == REDACTED


def test_structured_log_processor_redacts_authorization() -> None:
    event = redact_structlog_event(None, "info", {"event": "request", "authorization": "x"})

    assert event == {"event": "request", "authorization": REDACTED}


def test_jwt_rotation_accepts_previous_secret() -> None:
    old_secret = "old-secret-with-at-least-thirty-two-characters"
    new_secret = "new-secret-with-at-least-thirty-two-characters"
    source = Settings(app_env="testing", jwt_secret=old_secret)
    target = Settings(
        app_env="testing",
        jwt_secret=new_secret,
        jwt_previous_secrets=[old_secret],
    )
    user_id = uuid4()
    token, _ = create_access_token(
        source,
        user_id=user_id,
        session_id=uuid4(),
        company_id=uuid4(),
    )

    assert decode_access_token(target, token).user_id == user_id


def test_security_headers_are_applied(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_request_body_limit_rejects_oversized_payload() -> None:
    settings = Settings(app_env="testing", log_level="CRITICAL", request_max_body_bytes=1_024)
    with TestClient(create_app(settings)) as client:
        response = client.post("/unknown", content=b"x" * 1_025)

    assert response.status_code == 413
    assert response.json()["request_id"]
    assert response.headers["x-content-type-options"] == "nosniff"
