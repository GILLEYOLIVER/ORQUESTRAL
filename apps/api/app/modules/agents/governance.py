from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import Agent, AgentBudget, AgentVersion


class AgentBudgetExceededError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ToolAutonomyDecision:
    allowed: bool
    requires_approval: bool
    reason: str


def evaluate_tool_autonomy(*, autonomy_level: int, risk_level: str) -> ToolAutonomyDecision:
    if autonomy_level <= 0:
        return ToolAutonomyDecision(False, False, "Agente configurado somente para consulta.")
    if autonomy_level == 1:
        return ToolAutonomyDecision(False, False, "Agente configurado somente para recomendação.")
    if autonomy_level == 2:
        return ToolAutonomyDecision(True, True, "Execução supervisionada exige aprovação humana.")
    if risk_level in {"high", "critical"}:
        return ToolAutonomyDecision(True, True, "Ação de alto risco exige aprovação humana.")
    return ToolAutonomyDecision(True, False, "Ação autorizada pela política de autonomia.")


def agent_version_payload(agent: Agent, **overrides: Any) -> dict[str, Any]:
    payload = {
        "instructions": agent.instructions,
        "provider": agent.provider,
        "model": agent.model,
        "temperature": agent.temperature,
        "max_input_tokens": agent.max_input_tokens,
        "max_output_tokens": agent.max_output_tokens,
        "memory_enabled": agent.memory_enabled,
        "knowledge_base_id": agent.knowledge_base_id,
        "autonomy_level": 2,
        "max_steps": 12,
        "max_runtime_seconds": 120,
        "max_cost_per_run_microunits": 1_000_000,
    }
    payload.update(overrides)
    return payload


def version_checksum(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def active_agent_version(
    database: AsyncSession, *, agent: Agent, company_id: UUID
) -> AgentVersion | None:
    if agent.active_version_id is None:
        return None
    return cast(
        AgentVersion | None,
        await database.scalar(
            select(AgentVersion).where(
                AgentVersion.id == agent.active_version_id,
                AgentVersion.agent_id == agent.id,
                AgentVersion.company_id == company_id,
                AgentVersion.status == "published",
            )
        ),
    )


async def reserve_agent_budget(
    database: AsyncSession,
    *,
    company_id: UUID,
    agent_id: UUID,
    requested_microunits: int,
) -> tuple[AgentBudget, int]:
    budget = await database.scalar(
        select(AgentBudget)
        .where(AgentBudget.company_id == company_id, AgentBudget.agent_id == agent_id)
        .with_for_update()
    )
    if budget is None:
        raise AgentBudgetExceededError("Orçamento do agente não foi configurado.")
    now = datetime.now(UTC)
    if now >= budget.cycle_ends_at:
        budget.cycle_started_at = now
        budget.cycle_ends_at = _next_month(now)
        budget.reserved_microunits = 0
        budget.consumed_microunits = 0
    reservation = max(0, requested_microunits)
    projected = budget.consumed_microunits + budget.reserved_microunits + reservation
    if budget.hard_limit and budget.limit_microunits > 0 and projected > budget.limit_microunits:
        raise AgentBudgetExceededError("O orçamento mensal deste agente foi atingido.")
    budget.reserved_microunits += reservation
    return budget, reservation


async def settle_agent_budget(
    database: AsyncSession,
    *,
    company_id: UUID,
    agent_id: UUID,
    reserved_microunits: int,
    consumed_microunits: int,
) -> AgentBudget:
    budget = await database.scalar(
        select(AgentBudget)
        .where(AgentBudget.company_id == company_id, AgentBudget.agent_id == agent_id)
        .with_for_update()
    )
    if budget is None:
        raise AgentBudgetExceededError("Orçamento do agente não foi configurado.")
    budget.reserved_microunits = max(0, budget.reserved_microunits - reserved_microunits)
    budget.consumed_microunits += max(0, consumed_microunits)
    return budget


def _next_month(value: datetime) -> datetime:
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1, day=1)
    return value.replace(month=value.month + 1, day=1)
