from __future__ import annotations

from types import SimpleNamespace

import pytest
from redis.exceptions import RedisError
from starlette.requests import Request

from app.core.config import Settings
from app.core.middleware import SecurityMiddleware, client_ip_address, request_rate_limit_policy


class FakeRedis:
    def __init__(self, *, fail: bool = False) -> None:
        self.counts: dict[str, int] = {}
        self.fail = fail

    async def incr(self, key: str) -> int:
        if self.fail:
            raise RedisError("unavailable")
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> bool:
        return True

    async def ttl(self, key: str) -> int:
        return 120


def request_for(
    path: str,
    *,
    method: str = "POST",
    client: tuple[str, int] = ("198.51.100.10", 50000),
    forwarded_for: str | None = None,
    redis: FakeRedis | None = None,
) -> Request:
    headers = []
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    app = SimpleNamespace(
        state=SimpleNamespace(resources=SimpleNamespace(redis=redis or FakeRedis()))
    )
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "https",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers,
            "client": client,
            "server": ("testserver", 443),
            "app": app,
        }
    )


def test_forwarded_ip_is_ignored_from_untrusted_clients() -> None:
    request = request_for("/auth/login", forwarded_for="203.0.113.20")

    assert client_ip_address(request, Settings(app_env="testing")) == "198.51.100.10"


def test_forwarded_ip_is_used_only_from_configured_proxy() -> None:
    request = request_for(
        "/auth/login",
        client=("172.18.0.2", 50000),
        forwarded_for="203.0.113.20, 198.51.100.2",
    )
    settings = Settings(app_env="testing", security_trusted_proxy_ips=["172.18.0.2"])

    assert client_ip_address(request, settings) == "203.0.113.20"


def test_authentication_uses_a_stricter_rate_limit_policy() -> None:
    settings = Settings(app_env="testing")

    auth = request_rate_limit_policy(request_for("/auth/login"), settings)
    api = request_rate_limit_policy(request_for("/contacts", method="GET"), settings)

    assert auth.scope == "authentication"
    assert auth.requests == settings.security_auth_rate_limit_requests
    assert auth.fail_closed is True
    assert api.scope == "api"


@pytest.mark.asyncio
async def test_sensitive_rate_limit_returns_429_with_retry_headers() -> None:
    redis = FakeRedis()
    request = request_for("/auth/login", redis=redis)
    settings = Settings(
        app_env="local",
        security_auth_rate_limit_requests=5,
        login_ip_max_attempts=5,
        password_reset_ip_max_attempts=5,
    )
    middleware = SecurityMiddleware(lambda scope, receive, send: None)

    for _ in range(5):
        assert await middleware._enforce_rate_limit(request, settings) is None
    response = await middleware._enforce_rate_limit(request, settings)

    assert response is not None
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "120"
    assert response.headers["RateLimit-Remaining"] == "0"


@pytest.mark.asyncio
async def test_sensitive_rate_limit_fails_closed_without_redis() -> None:
    request = request_for("/auth/login", redis=FakeRedis(fail=True))
    settings = Settings(app_env="local")
    middleware = SecurityMiddleware(lambda scope, receive, send: None)

    response = await middleware._enforce_rate_limit(request, settings)

    assert response is not None
    assert response.status_code == 503
