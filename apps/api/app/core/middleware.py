from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from time import perf_counter
from typing import cast

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.request_context import normalize_request_id
from app.core.security import InvalidAccessTokenError, decode_access_token, hash_opaque_token
from app.modules.audit.service import AuditEventInput, AuditService

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_SENSITIVE_AUTH_PATHS = frozenset(
    {
        "/auth/accept-invitation",
        "/auth/development-login",
        "/auth/forgot-password",
        "/auth/login",
        "/auth/read-only-links",
        "/auth/read-only-links/authorize",
        "/auth/read-only-links/exchange",
        "/auth/refresh",
        "/auth/reset-password",
    }
)


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    scope: str
    requests: int
    window_seconds: int
    fail_closed: bool


def request_rate_limit_policy(request: Request, settings: Settings) -> RateLimitPolicy:
    if request.method == "POST" and request.url.path in _SENSITIVE_AUTH_PATHS:
        return RateLimitPolicy(
            scope="authentication",
            requests=settings.security_auth_rate_limit_requests,
            window_seconds=settings.security_auth_rate_limit_window_seconds,
            fail_closed=True,
        )
    return RateLimitPolicy(
        scope="api",
        requests=settings.security_rate_limit_requests,
        window_seconds=settings.security_rate_limit_window_seconds,
        fail_closed=False,
    )


def client_ip_address(request: Request, settings: Settings | None = None) -> str:
    direct = request.client.host if request.client else "unknown"
    forwarded = ""
    if settings is not None and direct in settings.security_trusted_proxy_ips:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", maxsplit=1)[0].strip()
    candidate = forwarded or direct
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return "unknown"


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = cast(Settings, request.app.state.settings)
        response = self._validate_body_size(request, settings)
        if response is None:
            response = self._validate_request_origin(request, settings)
        if response is None:
            response = self._validate_content_type(request, settings)
        if response is None:
            response = self._enforce_read_only(request, settings)
        if response is None:
            response = await self._enforce_rate_limit(request, settings)
        if response is None:
            response = await call_next(request)

        self._apply_security_headers(request, response, settings)
        if (
            settings.audit_capture_enabled
            and settings.app_env != "testing"
            and request.method in _MUTATING_METHODS
        ):
            await self._capture_audit_event(request, response, settings)
        return response

    @staticmethod
    def _problem(request: Request, status_code: int, title: str, detail: str) -> JSONResponse:
        request_id = getattr(request.state, "request_id", normalize_request_id(None))
        return JSONResponse(
            status_code=status_code,
            content={
                "type": "about:blank",
                "title": title,
                "status": status_code,
                "detail": detail,
                "instance": request.url.path,
                "request_id": request_id,
            },
        )

    def _validate_body_size(self, request: Request, settings: Settings) -> Response | None:
        header = request.headers.get("content-length")
        if not header:
            return None
        try:
            content_length = int(header)
        except ValueError:
            return self._problem(request, 400, "Cabeçalho inválido", "Content-Length inválido.")
        if content_length < 0:
            return self._problem(request, 400, "Cabeçalho inválido", "Content-Length inválido.")
        if content_length > settings.request_max_body_bytes:
            return self._problem(
                request,
                413,
                "Conteúdo muito grande",
                "A solicitação excede o limite de tamanho permitido.",
            )
        return None

    def _validate_request_origin(self, request: Request, settings: Settings) -> Response | None:
        if (
            not settings.security_enforce_origin
            or request.method not in _MUTATING_METHODS
            or settings.app_env == "testing"
        ):
            return None
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in {
            allowed.rstrip("/") for allowed in settings.cors_origins
        }:
            return self._problem(
                request,
                403,
                "Origem não autorizada",
                "A origem da solicitação não possui permissão para alterar dados.",
            )
        fetch_site = request.headers.get("sec-fetch-site", "").lower()
        if fetch_site == "cross-site" and not origin:
            return self._problem(
                request,
                403,
                "Solicitação bloqueada",
                "Solicitações mutáveis entre sites exigem uma origem autorizada.",
            )
        return None

    def _validate_content_type(self, request: Request, settings: Settings) -> Response | None:
        if (
            not settings.security_enforce_json_content_type
            or request.method not in {"POST", "PUT", "PATCH"}
            or settings.app_env == "testing"
        ):
            return None
        content_length = int(request.headers.get("content-length", "0") or "0")
        if content_length == 0:
            return None
        content_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0].lower()
        if content_type in {"application/json", "multipart/form-data"} or content_type.endswith(
            "+json"
        ):
            return None
        return self._problem(
            request,
            415,
            "Tipo de conteúdo não permitido",
            "Envie dados estruturados em JSON ou arquivos em multipart/form-data.",
        )

    async def _enforce_rate_limit(self, request: Request, settings: Settings) -> Response | None:
        if not settings.security_rate_limit_enabled or settings.app_env == "testing":
            return None
        policy = request_rate_limit_policy(request, settings)
        identity = client_ip_address(request, settings)
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            try:
                claims = decode_access_token(settings, authorization[7:].strip())
                identity = f"{identity}:{claims.user_id}"
            except InvalidAccessTokenError:
                pass
        fingerprint = hash_opaque_token(settings, f"{policy.scope}|{identity}")
        bucket = f"security:rate:{policy.scope}:{fingerprint}"
        redis = cast(Redis, request.app.state.resources.redis)
        try:
            count = await redis.incr(bucket)
            if count == 1:
                await redis.expire(bucket, policy.window_seconds)
            if count <= policy.requests:
                return None
            ttl = max(await redis.ttl(bucket), 1)
        except RedisError:
            get_logger(component="security").exception("rate_limit_backend_unavailable")
            if policy.fail_closed or settings.app_env in {"staging", "production"}:
                return self._problem(
                    request,
                    503,
                    "Proteção temporariamente indisponível",
                    "Tente novamente em alguns instantes.",
                )
            return None
        response = self._problem(
            request,
            429,
            "Muitas solicitações",
            "Aguarde alguns instantes antes de tentar novamente.",
        )
        response.headers["Retry-After"] = str(ttl)
        response.headers["RateLimit-Limit"] = str(policy.requests)
        response.headers["RateLimit-Remaining"] = "0"
        response.headers["RateLimit-Reset"] = str(ttl)
        return response

    def _enforce_read_only(self, request: Request, settings: Settings) -> Response | None:
        if request.method not in _MUTATING_METHODS or request.url.path == "/auth/logout":
            return None
        authorization = request.headers.get("authorization", "")
        if not authorization.lower().startswith("bearer "):
            return None
        try:
            claims = decode_access_token(settings, authorization[7:].strip())
        except InvalidAccessTokenError:
            return None
        if claims.access_mode != "read_only":
            return None
        return self._problem(
            request,
            403,
            "Acesso somente leitura",
            "Este acesso permite visualizar a Orkestral, mas não permite alterar dados.",
        )

    @staticmethod
    def _apply_security_headers(request: Request, response: Response, settings: Settings) -> None:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["X-Download-Options"] = "noopen"
        response.headers["Origin-Agent-Cluster"] = "?1"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
        if settings.web_static_directory and (
            request.url.path in {"/", "/login", "/acesso-socio", "/selecionar-empresa", "/app"}
            or request.url.path.startswith("/app/")
            or request.url.path.startswith("/assets/")
        ):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; "
                "script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "font-src 'self' data:; img-src 'self' data:; connect-src 'self'"
            )
        if settings.remote_development_enabled:
            response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        if settings.auth_cookie_secure and settings.security_hsts_seconds:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={settings.security_hsts_seconds}; includeSubDomains"
            )

    @staticmethod
    async def _capture_audit_event(
        request: Request, response: Response, settings: Settings
    ) -> None:
        user_id = None
        company_id = None
        actor_type = "anonymous"
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            try:
                claims = decode_access_token(settings, authorization[7:].strip())
                user_id = claims.user_id
                company_id = claims.company_id
                actor_type = "user"
            except InvalidAccessTokenError:
                pass
        route = request.scope.get("route")
        resource_type = str(getattr(route, "path", request.url.path))[:120]
        try:
            async with request.app.state.resources.sessions() as database:
                await AuditService(database).record(
                    AuditEventInput(
                        company_id=company_id,
                        actor_user_id=user_id,
                        actor_type=actor_type,
                        action=f"http.{request.method.lower()}",
                        resource_type=resource_type,
                        resource_id=None,
                        before_data=None,
                        after_data={"status_code": response.status_code},
                        ip_address=client_ip_address(request, settings),
                        user_agent=request.headers.get("user-agent"),
                        request_id=getattr(request.state, "request_id", normalize_request_id(None)),
                    )
                )
                await database.commit()
        except Exception:
            get_logger(component="audit").exception(
                "audit_capture_failed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
            )


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = normalize_request_id(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id
        started_at = perf_counter()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        duration_ms = round((perf_counter() - started_at) * 1_000, 2)
        response.headers["X-Request-ID"] = request_id
        get_logger(component="http").info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        structlog.contextvars.clear_contextvars()
        return response
