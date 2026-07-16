from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy import text

from app.core.config import Settings
from app.core.resources import ApplicationResources
from app.core.schemas import CheckResult

Check = Callable[[], Awaitable[None]]


@dataclass(slots=True)
class ReadinessReport:
    ready: bool
    checks: dict[str, CheckResult]


class ReadinessService:
    def __init__(self, resources: ApplicationResources, settings: Settings) -> None:
        self._resources = resources
        self._settings = settings

    async def _database(self) -> None:
        async with self._resources.database.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def _redis(self) -> None:
        if not await self._resources.redis.ping():
            raise ConnectionError("Redis indisponível")

    async def _configuration(self) -> None:
        if not self._settings.readiness_is_configured():
            raise RuntimeError("Configuração incompleta")

    async def _run_check(self, check: Check) -> CheckResult:
        started_at = perf_counter()
        try:
            await asyncio.wait_for(check(), timeout=self._settings.dependency_timeout_seconds)
            status = "ok"
        except Exception:
            # Dependências podem encapsular falhas de rede em exceções próprias.
            # O endpoint deve permanecer sanitizado e responder 503, nunca 500.
            status = "error"
        return CheckResult(
            status=status,
            latency_ms=round((perf_counter() - started_at) * 1_000, 2),
        )

    async def run(self) -> ReadinessReport:
        names = ("configuration", "postgresql", "redis")
        results = await asyncio.gather(
            self._run_check(self._configuration),
            self._run_check(self._database),
            self._run_check(self._redis),
        )
        checks = dict(zip(names, results, strict=True))
        return ReadinessReport(
            ready=all(result.status == "ok" for result in results),
            checks=checks,
        )
