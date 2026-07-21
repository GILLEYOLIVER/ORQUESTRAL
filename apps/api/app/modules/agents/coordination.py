from __future__ import annotations

import hashlib
from dataclasses import dataclass


class AgentCoordinationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ContractLimits:
    max_steps: int
    max_cost_microunits: int
    allowed_tool_keys: tuple[str, ...]


DELEGATION_TRANSITIONS = {
    "queued": {"start": "in_progress", "cancel": "cancelled"},
    "in_progress": {
        "complete": "completed",
        "fail": "failed",
        "cancel": "cancelled",
    },
}


def validate_task_contract(
    *,
    supervisor_autonomy_level: int,
    worker_max_steps: int,
    worker_max_cost_microunits: int,
    worker_tool_keys: set[str],
    requested: ContractLimits,
) -> None:
    if supervisor_autonomy_level < 4:
        raise AgentCoordinationError("O agente supervisor exige autonomia nível 4.")
    if requested.max_steps > worker_max_steps:
        raise AgentCoordinationError("O contrato excede o limite de passos do especialista.")
    if requested.max_cost_microunits > worker_max_cost_microunits:
        raise AgentCoordinationError("O contrato excede o orçamento por execução do especialista.")
    unknown = sorted(set(requested.allowed_tool_keys) - worker_tool_keys)
    if unknown:
        raise AgentCoordinationError(
            f"Ferramentas não autorizadas para o especialista: {', '.join(unknown)}."
        )


def transition_delegation(current_status: str, action: str) -> str:
    target = DELEGATION_TRANSITIONS.get(current_status, {}).get(action)
    if target is None:
        raise AgentCoordinationError(
            f"Transição {action} não permitida para delegação {current_status}."
        )
    return target


def coordination_fingerprint(*, company_id: object, value: str) -> str:
    return hashlib.sha256(f"{company_id}:{value}".encode()).hexdigest()
