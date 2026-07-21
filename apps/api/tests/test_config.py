from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.core.config import Environment, Settings


def production_settings(
    *,
    app_env: Environment = "production",
    development_expose_tokens: bool = False,
    bootstrap_enabled: bool = False,
    database_url: str = "postgresql+asyncpg://orkestral:strong-password@database.internal/orkestral",
    knowledge_embedding_provider: str = "openai_compatible",
    billing_enforcement_enabled: bool = True,
) -> Settings:
    return Settings(
        app_env=app_env,
        database_url=database_url,
        redis_url="rediss://redis.internal:6379/0",
        celery_broker_url="rediss://redis.internal:6379/1",
        celery_result_backend="rediss://redis.internal:6379/2",
        n8n_base_url="https://automation.internal",
        storage_endpoint="https://objects.internal",
        cors_origins=["https://app.orkestral.com.br"],
        jwt_secret="production-jwt-secret-with-at-least-32-characters",  # noqa: S106
        encryption_key="production-encryption-key-at-least-32-characters",
        encryption_key_provider="external",
        encryption_key_reference="vault://orkestral/production/active",
        agent_memory_monitor_secret="production-monitor-secret-with-at-least-32-characters",  # noqa: S106
        agent_memory_monitor_secret_rotated_at=datetime.now(UTC),
        n8n_api_key="production-n8n-key-with-at-least-32-characters",
        storage_access_key="production-storage-access-key-32-characters",
        storage_secret_key="production-storage-secret-key-32-characters",  # noqa: S106
        ai_provider_api_key="production-ai-provider-key-with-32-characters",
        knowledge_embedding_provider=knowledge_embedding_provider,
        billing_enforcement_enabled=billing_enforcement_enabled,
        development_expose_tokens=development_expose_tokens,
        bootstrap_enabled=bootstrap_enabled,
    )


def test_production_rejects_development_secrets() -> None:
    with pytest.raises(ValidationError, match="Valores inseguros para produção"):
        Settings(app_env="production")


def test_staging_uses_production_security_validation() -> None:
    with pytest.raises(ValidationError, match="Valores inseguros para produção"):
        Settings(app_env="staging")


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


def test_production_requires_billing_enforcement() -> None:
    with pytest.raises(ValidationError, match="BILLING_ENFORCEMENT_ENABLED"):
        production_settings(billing_enforcement_enabled=False)


def test_external_key_provider_requires_coordinated_previous_references() -> None:
    with pytest.raises(ValidationError):
        Settings(
            encryption_key_provider="external",
            encryption_key_reference="vault://orkestral/development/active",
            encryption_previous_keys=["historical-key-material-with-32-characters"],
            encryption_previous_key_references=[],
        )


def test_monitor_secret_rotation_rejects_duplicate_keyring() -> None:
    with pytest.raises(ValidationError, match="devem ser únicos"):
        Settings(
            agent_memory_monitor_previous_secrets=[
                "development-only-change-me-agent-memory-monitor-secret-32"
            ]
        )


def test_monitor_secret_rotation_rejects_expired_secret() -> None:
    with pytest.raises(ValidationError, match="idade máxima"):
        Settings(agent_memory_monitor_secret_rotated_at=datetime.now(UTC) - timedelta(days=91))


def test_local_monitor_secret_rotation_accepts_empty_environment_value() -> None:
    assert (
        Settings(agent_memory_monitor_secret_rotated_at="").agent_memory_monitor_secret_rotated_at
        is None
    )


def test_monitor_secret_rotation_warning_precedes_expiration() -> None:
    with pytest.raises(ValidationError, match="antes da idade máxima"):
        Settings(
            agent_memory_monitor_secret_max_age_days=14,
            agent_memory_monitor_secret_rotation_warning_days=14,
        )


def test_monitor_rotation_policy_is_environment_specific() -> None:
    assert Settings(app_env="local").agent_memory_monitor_effective_rotation_policy == "optional"
    assert Settings(app_env="development").agent_memory_monitor_effective_rotation_policy == "warn"
    with pytest.raises(ValueError, match="não aceita política optional"):
        Settings(
            app_env="development",
            agent_memory_monitor_secret_rotation_policy="optional",  # noqa: S106
        )
    with pytest.raises(ValueError, match="Política enforce"):
        Settings(
            app_env="local",
            agent_memory_monitor_secret_rotation_policy="enforce",  # noqa: S106
        )
