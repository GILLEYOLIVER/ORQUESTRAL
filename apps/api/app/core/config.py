from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "testing", "staging", "production"]

_PLACEHOLDER_MARKERS = ("change-me", "development-only", "example", "placeholder")


class Settings(BaseSettings):
    """Configuração central; todos os valores podem ser sobrescritos por ambiente."""

    model_config = SettingsConfigDict(
        env_file=None,
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Orkestral API"
    app_env: Environment = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://orkestral:development-only@localhost:5432/orkestral"
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")
    celery_broker_url: RedisDsn = RedisDsn("redis://localhost:6379/1")
    celery_result_backend: RedisDsn = RedisDsn("redis://localhost:6379/2")
    jwt_secret: str = "development-only-change-me-jwt-secret-32-chars"  # noqa: S105
    encryption_key: str = "development-only-change-me-encryption-key-32"
    n8n_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:5678")
    n8n_api_key: str = "development-only-change-me-n8n-api-key"
    storage_endpoint: AnyHttpUrl = AnyHttpUrl("http://localhost:9000")
    storage_access_key: str = "development-only"
    storage_secret_key: str = "development-only-change-me-storage-secret"  # noqa: S105
    storage_bucket: str = "orkestral"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost", "http://localhost:5173"]
    )
    dependency_timeout_seconds: float = Field(default=2.0, gt=0, le=10)

    @model_validator(mode="after")
    def reject_unsafe_production_values(self) -> Settings:
        if self.app_env != "production":
            return self

        secrets = {
            "JWT_SECRET": self.jwt_secret,
            "ENCRYPTION_KEY": self.encryption_key,
            "N8N_API_KEY": self.n8n_api_key,
            "STORAGE_ACCESS_KEY": self.storage_access_key,
            "STORAGE_SECRET_KEY": self.storage_secret_key,
        }
        unsafe = [
            name
            for name, value in secrets.items()
            if len(value) < 32 or any(marker in value.lower() for marker in _PLACEHOLDER_MARKERS)
        ]
        if unsafe:
            joined = ", ".join(sorted(unsafe))
            raise ValueError(f"Valores inseguros para produção: {joined}")
        return self

    def readiness_is_configured(self) -> bool:
        return bool(
            self.database_url and self.redis_url and self.storage_bucket and self.n8n_base_url
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
