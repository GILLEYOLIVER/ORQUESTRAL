from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


def remote_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "development",
        "remote_development_enabled": True,
        "database_url": "postgresql+asyncpg://user:password@db.example/orkestral?ssl=require",
        "redis_url": "rediss://default:password@redis.example:6379/0",
        "celery_broker_url": "rediss://default:password@redis.example:6379/1",
        "celery_result_backend": "rediss://default:password@redis.example:6379/2",
        "jwt_secret": "j" * 48,
        "encryption_key": "e" * 48,
        "cors_origins": [],
        "development_expose_tokens": False,
        "bootstrap_enabled": False,
        "n8n_enabled": False,
        "object_storage_enabled": False,
        "background_worker_enabled": False,
        "email_delivery_enabled": False,
        "git_commit_sha": "abc123",
        "log_level": "CRITICAL",
    }
    values.update(overrides)
    return Settings(**values)


def test_remote_development_rejects_local_connections() -> None:
    with pytest.raises(ValidationError, match="Conexões locais"):
        remote_settings(database_url="postgresql+asyncpg://user:password@localhost/db")


def test_remote_development_rejects_token_preview() -> None:
    with pytest.raises(ValidationError, match="DEVELOPMENT_EXPOSE_TOKENS"):
        remote_settings(development_expose_tokens=True)


def test_system_metadata_and_reduced_capabilities() -> None:
    app = create_app(remote_settings())
    with TestClient(app) as client:
        version = client.get("/system/version")
        capabilities = client.get("/system/capabilities")

    assert version.status_code == 200
    assert version.json()["commit"] == "abc123"
    assert version.headers["x-robots-tag"] == "noindex, nofollow, noarchive"
    assert capabilities.json() == {
        "remote_development": True,
        "n8n": False,
        "object_storage": False,
        "background_worker": False,
        "email_delivery": False,
    }


def test_static_spa_is_served_when_configured(tmp_path: Path) -> None:
    index = tmp_path / "index.html"
    index.write_text("<main>Orkestral remoto</main>", encoding="utf-8")
    app = create_app(remote_settings(web_static_directory=str(tmp_path)))
    with TestClient(app) as client:
        response = client.get("/app/agentes")
        robots = client.get("/robots.txt")

    assert response.status_code == 200
    assert "Orkestral remoto" in response.text
    assert "Disallow: /" in robots.text
