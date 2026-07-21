from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "development", "testing", "staging", "production"]

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
    app_env: Environment = "local"
    app_version: str = "0.13.0"
    log_level: str = "INFO"
    remote_development_enabled: bool = False
    n8n_enabled: bool = True
    object_storage_enabled: bool = True
    background_worker_enabled: bool = True
    email_delivery_enabled: bool = True
    web_static_directory: str | None = None
    git_commit_sha: str = "local"
    render_git_commit: str | None = None
    deployed_at: str | None = None
    database_url: str = "postgresql+asyncpg://orkestral:development-only@localhost:5432/orkestral"
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")
    celery_broker_url: RedisDsn = RedisDsn("redis://localhost:6379/1")
    celery_result_backend: RedisDsn = RedisDsn("redis://localhost:6379/2")
    jwt_secret: str = "development-only-change-me-jwt-secret-32-chars"  # noqa: S105
    encryption_key: str = "development-only-change-me-encryption-key-32"
    encryption_key_provider: Literal["environment", "external"] = "environment"
    encryption_key_reference: str = "environment://orkestral/local/active"
    encryption_previous_key_references: list[str] = Field(default_factory=list)
    agent_memory_monitor_secret: str = "development-only-change-me-agent-memory-monitor-secret-32"  # noqa: S105
    agent_memory_monitor_previous_secrets: list[str] = Field(default_factory=list)
    agent_memory_reencryption_terminal_retention_days: int = Field(default=90, ge=7, le=3_650)
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
    knowledge_embedding_provider: Literal["local_hash", "openai_compatible"] = "local_hash"
    knowledge_embedding_model: str = "text-embedding-3-small"
    knowledge_embedding_dimensions: int = 384
    knowledge_embedding_batch_size: int = Field(default=32, ge=1, le=256)
    storage_endpoint: AnyHttpUrl = AnyHttpUrl("http://localhost:9000")
    storage_access_key: str = "development-only"
    storage_secret_key: str = "development-only-change-me-storage-secret"  # noqa: S105
    storage_bucket: str = "orkestral"
    object_storage_sse_enabled: bool = False
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost", "http://localhost:5173"]
    )
    security_rate_limit_enabled: bool = True
    security_rate_limit_requests: int = Field(default=300, ge=10, le=10_000)
    security_rate_limit_window_seconds: int = Field(default=60, ge=10, le=3_600)
    request_max_body_bytes: int = Field(default=26_214_400, ge=1_024, le=104_857_600)
    security_hsts_seconds: int = Field(default=31_536_000, ge=0, le=63_072_000)
    security_trusted_proxy_ips: list[str] = Field(default_factory=list)
    security_enforce_origin: bool = True
    security_enforce_json_content_type: bool = True
    encryption_previous_keys: list[str] = Field(default_factory=list)
    audit_capture_enabled: bool = True
    audit_retention_days: int = Field(default=365, ge=30, le=3_650)
    billing_enforcement_enabled: bool = False
    notification_email_webhook_url: str | None = None
    notification_whatsapp_webhook_url: str | None = None
    notification_delivery_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    notification_reminder_minutes: int = Field(default=30, ge=1, le=10_080)
    dependency_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
    jwt_issuer: str = "orkestral"
    jwt_audience: str = "orkestral-api"
    jwt_previous_secrets: list[str] = Field(default_factory=list)
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

    @field_validator("knowledge_embedding_dimensions")
    @classmethod
    def validate_knowledge_embedding_dimensions(cls, value: int) -> int:
        if value != 384:
            raise ValueError("KNOWLEDGE_EMBEDDING_DIMENSIONS must be 384")
        return value

    @model_validator(mode="after")
    def reject_unsafe_production_values(self) -> Settings:
        monitor_secrets = (
            self.agent_memory_monitor_secret,
            *self.agent_memory_monitor_previous_secrets,
        )
        if len(set(monitor_secrets)) != len(monitor_secrets):
            raise ValueError("Segredos ativos e anteriores do monitor devem ser únicos")
        if self.encryption_key_provider == "external":
            references = (
                self.encryption_key_reference,
                *self.encryption_previous_key_references,
            )
            if (
                not self.encryption_key_reference.strip()
                or any(
                    marker in value.lower()
                    for value in references
                    for marker in _PLACEHOLDER_MARKERS
                )
                or len(set(references)) != len(references)
                or len(self.encryption_previous_key_references)
                != len(self.encryption_previous_keys)
            ):
                raise ValueError(
                    "Referências do cofre externo devem ser únicas, seguras e corresponder ao keyring"
                )
        if self.remote_development_enabled:
            if self.app_env != "development":
                raise ValueError("REMOTE_DEVELOPMENT_ENABLED exige APP_ENV=development")
            remote_secrets = {
                "JWT_SECRET": self.jwt_secret,
                "ENCRYPTION_KEY": self.encryption_key,
                "AGENT_MEMORY_MONITOR_SECRET": self.agent_memory_monitor_secret,
            }
            unsafe_remote_secrets = [
                name
                for name, value in remote_secrets.items()
                if len(value) < 32
                or any(marker in value.lower() for marker in _PLACEHOLDER_MARKERS)
            ]
            if any(
                len(value) < 32 or any(marker in value.lower() for marker in _PLACEHOLDER_MARKERS)
                for value in self.agent_memory_monitor_previous_secrets
            ):
                unsafe_remote_secrets.append("AGENT_MEMORY_MONITOR_PREVIOUS_SECRETS")
            if unsafe_remote_secrets:
                raise ValueError(
                    "Segredos inseguros no desenvolvimento remoto: "
                    + ", ".join(unsafe_remote_secrets)
                )
            remote_connections = {
                "DATABASE_URL": self.database_url,
                "REDIS_URL": str(self.redis_url),
            }
            unsafe_remote_connections = [
                name
                for name, value in remote_connections.items()
                if "localhost" in value.lower() or "127.0.0.1" in value
            ]
            if unsafe_remote_connections:
                raise ValueError(
                    "Conexões locais no desenvolvimento remoto: "
                    + ", ".join(unsafe_remote_connections)
                )
            if self.development_expose_tokens:
                raise ValueError(
                    "DEVELOPMENT_EXPOSE_TOKENS deve permanecer desabilitado remotamente"
                )
            if self.bootstrap_enabled and not (
                self.bootstrap_admin_email and self.bootstrap_admin_password
            ):
                raise ValueError(
                    "Seed remoto exige BOOTSTRAP_ADMIN_EMAIL e BOOTSTRAP_ADMIN_PASSWORD"
                )
            if any(
                origin == "*" or not origin.startswith("https://") for origin in self.cors_origins
            ):
                raise ValueError(
                    "CORS_ORIGINS remoto aceita somente origens HTTPS explícitas ou lista vazia"
                )
        if self.app_env not in {"staging", "production"}:
            return self

        secrets = {
            "JWT_SECRET": self.jwt_secret,
            "ENCRYPTION_KEY": self.encryption_key,
            "AGENT_MEMORY_MONITOR_SECRET": self.agent_memory_monitor_secret,
            "N8N_API_KEY": self.n8n_api_key,
            "STORAGE_ACCESS_KEY": self.storage_access_key,
            "STORAGE_SECRET_KEY": self.storage_secret_key,
        }
        unsafe = [
            name
            for name, value in secrets.items()
            if len(value) < 32 or any(marker in value.lower() for marker in _PLACEHOLDER_MARKERS)
        ]
        if any(
            len(value) < 32 or any(marker in value.lower() for marker in _PLACEHOLDER_MARKERS)
            for value in self.agent_memory_monitor_previous_secrets
        ):
            unsafe.append("AGENT_MEMORY_MONITOR_PREVIOUS_SECRETS")
        if unsafe:
            joined = ", ".join(sorted(unsafe))
            raise ValueError(f"Valores inseguros para produção: {joined}")
        if self.encryption_key_provider != "external":
            raise ValueError("ENCRYPTION_KEY_PROVIDER deve utilizar cofre external em produção")

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
        if not self.billing_enforcement_enabled:
            raise ValueError("BILLING_ENFORCEMENT_ENABLED deve ser habilitado em produção")
        if self.knowledge_embedding_provider != "openai_compatible":
            raise ValueError("KNOWLEDGE_EMBEDDING_PROVIDER deve ser openai_compatible em produção")
        if not self.ai_provider_api_key or any(
            marker in self.ai_provider_api_key.lower() for marker in _PLACEHOLDER_MARKERS
        ):
            raise ValueError("AI_PROVIDER_API_KEY deve ser configurada para embeddings em produção")
        if any(origin == "*" or not origin.startswith("https://") for origin in self.cors_origins):
            raise ValueError("CORS_ORIGINS deve conter apenas origens HTTPS explícitas em produção")
        unsafe_previous_secrets = [
            value
            for value in self.jwt_previous_secrets
            if len(value) < 32 or any(marker in value.lower() for marker in _PLACEHOLDER_MARKERS)
        ]
        if unsafe_previous_secrets:
            raise ValueError("JWT_PREVIOUS_SECRETS contém valores inseguros para produção")
        return self

    @model_validator(mode="after")
    def enforce_encrypted_transports(self) -> Settings:
        remote = self.remote_development_enabled or self.app_env in {"staging", "production"}
        if not remote:
            return self
        database_value = self.database_url.lower()
        if "sslmode=require" not in database_value and "ssl=require" not in database_value:
            raise ValueError("DATABASE_URL remota deve exigir TLS com sslmode=require")
        if not str(self.redis_url).lower().startswith("rediss://"):
            raise ValueError("REDIS_URL remota deve utilizar TLS com rediss://")
        if self.object_storage_enabled and not str(self.storage_endpoint).lower().startswith(
            "https://"
        ):
            raise ValueError("STORAGE_ENDPOINT remoto deve utilizar HTTPS")
        if self.object_storage_enabled and not self.object_storage_sse_enabled:
            raise ValueError("OBJECT_STORAGE_SSE_ENABLED deve permanecer habilitado remotamente")
        unsafe_previous = [
            key
            for key in self.encryption_previous_keys
            if len(key) < 32 or any(marker in key.lower() for marker in _PLACEHOLDER_MARKERS)
        ]
        if unsafe_previous:
            raise ValueError("ENCRYPTION_PREVIOUS_KEYS contém chaves inseguras")
        return self

    @property
    def auth_cookie_secure(self) -> bool:
        return self.remote_development_enabled or self.app_env in {"staging", "production"}

    @property
    def effective_bootstrap_admin_password(self) -> str | None:
        if self.bootstrap_admin_password:
            return self.bootstrap_admin_password
        if self.app_env == "local" and self.bootstrap_admin_email:
            material = f"{self.jwt_secret}|{self.bootstrap_admin_email}|orkestral-local"
            digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
            return f"Local-{digest[:24]}!9Aa"
        return None

    @property
    def deployed_commit(self) -> str:
        return self.render_git_commit or self.git_commit_sha

    @property
    def jwt_verification_secrets(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((self.jwt_secret, *self.jwt_previous_secrets)))

    def readiness_is_configured(self) -> bool:
        required = [bool(self.database_url), bool(self.redis_url)]
        if self.object_storage_enabled:
            required.extend([bool(self.storage_endpoint), bool(self.storage_bucket)])
        if self.n8n_enabled:
            required.append(bool(self.n8n_base_url))
        return all(required)


@lru_cache
def get_settings() -> Settings:
    return Settings()
