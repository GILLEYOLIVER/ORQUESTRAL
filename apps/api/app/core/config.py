from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "testing", "staging", "production"]

_PLACEHOLDER_MARKERS = ("change-me", "development-only", "example", "placeholder")
_LOCAL_MARKERS = ("localhost", "127.0.0.1", "::1")


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
    app_version: str = "0.8.0"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://orkestral:development-only@localhost:5432/orkestral"
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")
    celery_broker_url: RedisDsn = RedisDsn("redis://localhost:6379/1")
    celery_result_backend: RedisDsn = RedisDsn("redis://localhost:6379/2")
    jwt_secret: str = "development-only-change-me-jwt-secret-32-chars"  # noqa: S105
    encryption_key: str = "development-only-change-me-encryption-key-32"
    n8n_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:5678")
    n8n_api_key: str = "development-only-change-me-n8n-api-key"
    n8n_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    n8n_max_attempts: int = Field(default=3, ge=1, le=5)
    workflow_webhook_rate_limit: int = Field(default=60, ge=1, le=1_000)
    workflow_max_payload_bytes: int = Field(default=262_144, ge=1_024, le=5_242_880)
    ai_provider_api_key: str | None = None
    ai_provider_base_url: AnyHttpUrl = AnyHttpUrl("https://api.openai.com/v1")
    ai_provider_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    ai_input_cost_per_million_tokens_microusd: int = Field(default=150_000, ge=0)
    ai_output_cost_per_million_tokens_microusd: int = Field(default=600_000, ge=0)
    knowledge_max_file_bytes: int = Field(default=20_971_520, ge=1_048_576, le=104_857_600)
    knowledge_web_allowed_domains: list[str] = Field(default_factory=list)
    storage_endpoint: AnyHttpUrl = AnyHttpUrl("http://localhost:9000")
    storage_access_key: str = "development-only"
    storage_secret_key: str = "development-only-change-me-storage-secret"  # noqa: S105
    storage_bucket: str = "orkestral"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost", "http://localhost:5173"]
    )
    dependency_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
    jwt_issuer: str = "orkestral"
    jwt_audience: str = "orkestral-api"
    access_token_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_days: int = Field(default=30, ge=1, le=90)
    password_reset_minutes: int = Field(default=30, ge=5, le=120)
    invitation_days: int = Field(default=7, ge=1, le=30)
    auth_cookie_name: str = "orkestral_refresh"
    login_max_attempts: int = Field(default=5, ge=3, le=20)
    login_window_seconds: int = Field(default=900, ge=60, le=3_600)
    development_expose_tokens: bool = False
    bootstrap_enabled: bool = False
    bootstrap_admin_name: str | None = None
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    bootstrap_company_name: str | None = None
    bootstrap_company_slug: str | None = None
    bootstrap_company_document: str | None = None

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

        configurations = {
            "DATABASE_URL": self.database_url,
            "REDIS_URL": str(self.redis_url),
            "CELERY_BROKER_URL": str(self.celery_broker_url),
            "CELERY_RESULT_BACKEND": str(self.celery_result_backend),
            "N8N_BASE_URL": str(self.n8n_base_url),
            "STORAGE_ENDPOINT": str(self.storage_endpoint),
            "CORS_ORIGINS": ",".join(self.cors_origins),
        }
        unsafe_configurations = [
            name
            for name, value in configurations.items()
            if any(marker in value.lower() for marker in (*_PLACEHOLDER_MARKERS, *_LOCAL_MARKERS))
        ]
        if unsafe_configurations:
            joined = ", ".join(sorted(unsafe_configurations))
            raise ValueError(f"Configurações inseguras para produção: {joined}")
        if self.development_expose_tokens:
            raise ValueError("DEVELOPMENT_EXPOSE_TOKENS não pode ser habilitado em produção")
        if self.bootstrap_enabled:
            raise ValueError("BOOTSTRAP_ENABLED não pode ser habilitado em produção")
        return self

    @property
    def auth_cookie_secure(self) -> bool:
        return self.app_env in {"staging", "production"}

    def readiness_is_configured(self) -> bool:
        return bool(
            self.database_url and self.redis_url and self.storage_bucket and self.n8n_base_url
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
