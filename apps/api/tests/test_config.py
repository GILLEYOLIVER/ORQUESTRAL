from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def production_settings(
    *,
    development_expose_tokens: bool = False,
    bootstrap_enabled: bool = False,
    database_url: str = "postgresql+asyncpg://orkestral:strong-password@database.internal/orkestral",
    knowledge_embedding_provider: str = "openai_compatible",
) -> Settings:
    return Settings(
        app_env="production",
        database_url=database_url,
        redis_url="rediss://redis.internal:6379/0",
        celery_broker_url="rediss://redis.internal:6379/1",
        celery_result_backend="rediss://redis.internal:6379/2",
        n8n_base_url="https://automation.internal",
        storage_endpoint="https://objects.internal",
        cors_origins=["https://app.orkestral.com.br"],
        jwt_secret="production-jwt-secret-with-at-least-32-characters",  # noqa: S106
        encryption_key="production-encryption-key-at-least-32-characters",
        n8n_api_key="production-n8n-key-with-at-least-32-characters",
        storage_access_key="production-storage-access-key-32-characters",
        storage_secret_key="production-storage-secret-key-32-characters",  # noqa: S106
        ai_provider_api_key="production-ai-provider-key-with-32-characters",
        knowledge_embedding_provider=knowledge_embedding_provider,
        development_expose_tokens=development_expose_tokens,
        bootstrap_enabled=bootstrap_enabled,
    )


def test_production_rejects_development_secrets() -> None:
    with pytest.raises(ValidationError, match="Valores inseguros para produção"):
        Settings(app_env="production")


def test_production_rejects_development_token_exposure() -> None:
    with pytest.raises(ValidationError, match="DEVELOPMENT_EXPOSE_TOKENS"):
        production_settings(development_expose_tokens=True)


def test_production_rejects_bootstrap() -> None:
    with pytest.raises(ValidationError, match="BOOTSTRAP_ENABLED"):
        production_settings(bootstrap_enabled=True)


def test_production_rejects_local_infrastructure() -> None:
    with pytest.raises(ValidationError, match="Configurações inseguras para produção"):
        production_settings(database_url="postgresql://localhost/db")


def test_production_rejects_local_embedding_fallback() -> None:
    with pytest.raises(ValidationError, match="KNOWLEDGE_EMBEDDING_PROVIDER"):
        production_settings(knowledge_embedding_provider="local_hash")
