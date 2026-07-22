from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utc_now
from app.modules.workflows.models import WorkflowProviderCircuit


class ProviderCircuitOpen(RuntimeError):
    def __init__(self, retry_at: object | None):
        super().__init__("O motor interno esta temporariamente protegido pelo circuit breaker.")
        self.retry_at = retry_at


async def _locked_circuit(
    database: AsyncSession, *, company_id: UUID, provider: str
) -> WorkflowProviderCircuit:
    circuit = await database.scalar(
        select(WorkflowProviderCircuit)
        .where(
            WorkflowProviderCircuit.company_id == company_id,
            WorkflowProviderCircuit.provider == provider,
        )
        .with_for_update()
    )
    if circuit is None:
        circuit = WorkflowProviderCircuit(
            company_id=company_id,
            provider=provider,
            state="closed",
            failure_count=0,
        )
        database.add(circuit)
        await database.flush()
    return circuit


async def ensure_provider_available(
    database: AsyncSession, *, company_id: UUID, provider: str
) -> None:
    circuit = await _locked_circuit(database, company_id=company_id, provider=provider)
    now = utc_now()
    if circuit.state == "open":
        if circuit.retry_at is not None and circuit.retry_at > now:
            raise ProviderCircuitOpen(circuit.retry_at)
        circuit.state = "half_open"
        circuit.updated_at = now


async def record_provider_success(
    database: AsyncSession, *, company_id: UUID, provider: str
) -> None:
    circuit = await _locked_circuit(database, company_id=company_id, provider=provider)
    circuit.state = "closed"
    circuit.failure_count = 0
    circuit.opened_at = None
    circuit.retry_at = None
    circuit.last_failure_code = None
    circuit.updated_at = utc_now()


async def record_provider_failure(
    database: AsyncSession,
    *,
    company_id: UUID,
    provider: str,
    error_code: str,
    threshold: int,
    reset_seconds: int,
) -> None:
    circuit = await _locked_circuit(database, company_id=company_id, provider=provider)
    now = utc_now()
    circuit.failure_count += 1
    circuit.last_failure_code = error_code[:120]
    circuit.updated_at = now
    if circuit.failure_count >= threshold or circuit.state == "half_open":
        circuit.state = "open"
        circuit.opened_at = now
        circuit.retry_at = now + timedelta(seconds=reset_seconds)


async def provider_circuit_snapshot(
    database: AsyncSession, *, company_id: UUID, provider: str
) -> dict[str, Any]:
    circuit = await database.scalar(
        select(WorkflowProviderCircuit).where(
            WorkflowProviderCircuit.company_id == company_id,
            WorkflowProviderCircuit.provider == provider,
        )
    )
    if circuit is None:
        return {"state": "closed", "failure_count": 0, "retry_at": None}
    return {
        "state": circuit.state,
        "failure_count": circuit.failure_count,
        "retry_at": circuit.retry_at,
    }
