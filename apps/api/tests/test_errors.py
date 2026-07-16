from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_unhandled_errors_do_not_expose_internal_details() -> None:
    app: FastAPI = create_app(Settings(app_env="testing", log_level="CRITICAL"))

    @app.get("/explode")
    async def explode() -> None:
        raise RuntimeError("database-password-super-secret")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/explode")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "database-password-super-secret" not in response.text
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
