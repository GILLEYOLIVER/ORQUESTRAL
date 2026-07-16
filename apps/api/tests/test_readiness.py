from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.schemas import CheckResult
from app.main import create_app
from app.routes.health import get_readiness_service
from app.services.readiness import ReadinessReport, ReadinessService


class FakeReadinessService:
    def __init__(self, ready: bool) -> None:
        self.ready = ready

    async def run(self) -> ReadinessReport:
        status = "ok" if self.ready else "error"
        return ReadinessReport(
            ready=self.ready,
            checks={
                "configuration": CheckResult(status="ok", latency_ms=0.1),
                "postgresql": CheckResult(status=status, latency_ms=0.2),
                "redis": CheckResult(status="ok", latency_ms=0.1),
            },
        )


def test_ready_returns_200_when_all_dependencies_are_available() -> None:
    app = create_app(Settings(app_env="testing", log_level="CRITICAL"))
    app.dependency_overrides[get_readiness_service] = lambda: FakeReadinessService(True)
    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_returns_sanitized_503_when_dependency_fails() -> None:
    app = create_app(Settings(app_env="testing", log_level="CRITICAL"))
    app.dependency_overrides[get_readiness_service] = lambda: FakeReadinessService(False)
    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["postgresql"] == {"status": "error", "latency_ms": 0.2}
    assert "detail" not in response.json()["checks"]["postgresql"]


async def test_dependency_exceptions_are_converted_to_sanitized_check_errors() -> None:
    service = object.__new__(ReadinessService)
    service._settings = Settings(app_env="testing", dependency_timeout_seconds=0.1)

    async def unexpected_driver_error() -> None:
        raise ValueError("credential-that-must-not-leak")

    result = await service._run_check(unexpected_driver_error)

    assert result.status == "error"
    assert result.model_dump().keys() == {"status", "latency_ms"}
