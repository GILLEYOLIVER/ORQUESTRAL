from __future__ import annotations

from typing import Any

from app.modules.workflows.definition import (
    ACTION_TYPES,
    TRIGGER_TYPES,
    analyze_definition,
    as_summary_object,
    execution_policy,
)


def simulate_definition(definition: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic dry-run trace without executing external effects."""
    issues = analyze_definition(definition)
    policy = execution_policy(definition)
    nodes = [item for item in definition.get("nodes", []) if isinstance(item, dict)]
    by_id = {str(item.get("id")): item for item in nodes}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in by_id}
    for edge in definition.get("connections", []):
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source in outgoing and target in by_id:
            outgoing[source].append(target)

    queue = [
        node_id for node_id, node in by_id.items() if str(node.get("type", "")) in TRIGGER_TYPES
    ]
    visited: set[str] = set()
    trace: list[dict[str, Any]] = []
    blocked_side_effects = 0
    max_steps = int(policy["max_steps"])
    while queue and len(trace) < max_steps:
        node_id = queue.pop(0)
        if node_id in visited:
            continue
        visited.add(node_id)
        node = by_id[node_id]
        block_type = str(node.get("type", ""))
        status = "simulated"
        detail = "Etapa validada sem executar operacoes externas."
        side_effect = block_type in ACTION_TYPES
        if block_type == "action.human_approval":
            status = "approval_required"
            detail = "A execucao real aguardaria aprovacao humana."
        elif side_effect:
            status = "blocked_effect"
            detail = "Efeito externo bloqueado pelo modo de simulacao."
        elif block_type == "logic.condition":
            detail = "Os dois caminhos foram analisados; a decisao real depende dos dados."
        elif block_type == "trigger.domain_event":
            config = node.get("config", {})
            detail = (
                f"Evento {config.get('event_type')} v{config.get('event_version')} reconhecido."
            )
        if side_effect:
            blocked_side_effects += 1
        trace.append(
            {
                "node_id": node_id,
                "label": str(node.get("label") or block_type)[:160],
                "block_type": block_type,
                "status": status,
                "detail": detail,
                "side_effect": side_effect,
            }
        )
        queue.extend(outgoing.get(node_id, []))

    if queue:
        issues.append(
            {
                "severity": "error",
                "code": "simulation_step_limit",
                "message": "A simulacao atingiu o limite de etapas da politica.",
                "node_id": None,
            }
        )
    valid = not any(item["severity"] == "error" for item in issues)
    return {
        "valid": valid,
        "publishable": valid,
        "estimated_steps": len(trace),
        "blocked_side_effects": blocked_side_effects,
        "execution_policy": policy,
        "input_summary": as_summary_object(input_data),
        "trace": trace,
        "issues": issues,
    }
