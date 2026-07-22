from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest

from app.core.security import utc_now
from app.modules.workflows.provider_resilience import (
    ProviderCircuitOpen,
    ensure_provider_available,
    record_provider_failure,
    record_provider_success,
)


class FakeCircuitDatabase:
    def __init__(self) -> None:
        self.circuit: Any | None = None

    async def scalar(self, _statement: object) -> Any | None:
        return self.circuit

    def add(self, value: Any) -> None:
        self.circuit = value

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_provider_circuit_opens_recovers_and_closes() -> None:
    database = FakeCircuitDatabase()
    company_id = uuid4()
    await record_provider_failure(
        database,  # type: ignore[arg-type]
        company_id=company_id,
        provider="n8n",
        error_code="timeout",
        threshold=2,
        reset_seconds=60,
    )
    assert database.circuit.state == "closed"
    await record_provider_failure(
        database,  # type: ignore[arg-type]
        company_id=company_id,
        provider="n8n",
        error_code="timeout",
        threshold=2,
        reset_seconds=60,
    )
    assert database.circuit.state == "open"
    with pytest.raises(ProviderCircuitOpen):
        await ensure_provider_available(
            database,
            company_id=company_id,
            provider="n8n",  # type: ignore[arg-type]
        )
    database.circuit.retry_at = utc_now() - timedelta(seconds=1)
    await ensure_provider_available(
        database,
        company_id=company_id,
        provider="n8n",  # type: ignore[arg-type]
    )
    assert database.circuit.state == "half_open"
    await record_provider_success(
        database,
        company_id=company_id,
        provider="n8n",  # type: ignore[arg-type]
    )
    assert database.circuit.state == "closed"
    assert database.circuit.failure_count == 0
