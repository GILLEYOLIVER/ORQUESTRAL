from __future__ import annotations

from typing import Any

from app.modules.workflows.definition import TRIGGER_TYPES, validate_definition


def _name(node: dict[str, Any]) -> str:
    label = str(node.get("label") or node["type"]).strip()[:90]
    return f"{label} [{str(node['id'])[:12]}]"


def _native_node(node: dict[str, Any], internal_webhook_path: str) -> dict[str, Any]:
    node_type = str(node["type"])
    config = node.get("config", {})
    position = node.get("position", {})
    base: dict[str, Any] = {
        "id": str(node["id"]),
        "name": _name(node),
        "position": [int(position.get("x", 0)), int(position.get("y", 0))],
        "parameters": {},
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
    }
    if node_type == "trigger.manual":
        base.update(type="n8n-nodes-base.manualTrigger", typeVersion=1)
    elif node_type == "trigger.schedule":
        minutes = max(1, int(config.get("interval_minutes", 60)))
        base.update(
            type="n8n-nodes-base.scheduleTrigger",
            typeVersion=1.2,
            parameters={"rule": {"interval": [{"field": "minutes", "minutesInterval": minutes}]}},
        )
    elif node_type in {"trigger.webhook", "trigger.message_received", "trigger.contact_created"}:
        suffix = str(node["id"]).lower().replace("_", "-")[:32]
        base.update(
            type="n8n-nodes-base.webhook",
            typeVersion=2,
            parameters={
                "httpMethod": "POST",
                "path": f"{internal_webhook_path}-{suffix}",
                "responseMode": "lastNode",
                "options": {},
            },
        )
    elif node_type == "logic.condition":
        expression = str(config.get("expression", "$json.input != null"))
        base.update(
            type="n8n-nodes-base.if",
            typeVersion=2.2,
            parameters={
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                    "conditions": [{
                        "id": f"condition-{node['id']}",
                        "leftValue": f"={{{{ {expression} }}}}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                    }],
                    "combinator": "and",
                },
                "options": {},
            },
        )
    elif node_type == "logic.wait":
        base.update(
            type="n8n-nodes-base.wait",
            typeVersion=1.1,
            parameters={"amount": max(1, int(config.get("seconds", 5))), "unit": "seconds"},
        )
    return base


def compile_definition(definition: dict[str, Any], *, internal_webhook_path: str) -> dict[str, Any]:
    validate_definition(definition)
    visual_nodes = [node for node in definition["nodes"] if isinstance(node, dict)]
    by_id = {str(node["id"]): node for node in visual_nodes}
    names = {node_id: _name(node) for node_id, node in by_id.items()}
    nodes = [_native_node(node, internal_webhook_path) for node in visual_nodes]
    internal_name = "Entrada interna Orkestral"
    min_x = min(int(node.get("position", {}).get("x", 0)) for node in visual_nodes)
    min_y = min(int(node.get("position", {}).get("y", 0)) for node in visual_nodes)
    nodes.append({
        "id": "orkestral-internal-entry",
        "name": internal_name,
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [min_x - 260, min_y + 120],
        "parameters": {
            "httpMethod": "POST",
            "path": internal_webhook_path,
            "responseMode": "lastNode",
            "options": {},
        },
    })

    connections: dict[str, dict[str, list[list[dict[str, Any]]]]] = {}

    def connect(source_name: str, target_name: str, output_index: int = 0) -> None:
        main = connections.setdefault(source_name, {"main": []})["main"]
        while len(main) <= output_index:
            main.append([])
        main[output_index].append({"node": target_name, "type": "main", "index": 0})

    trigger_successors: list[str] = []
    for edge in definition["connections"]:
        source_id = str(edge["source"])
        target_id = str(edge["target"])
        output_index = 1 if str(edge.get("source_handle", "main")) == "false" else 0
        connect(names[source_id], names[target_id], output_index)
        if str(by_id[source_id]["type"]) in TRIGGER_TYPES:
            trigger_successors.append(target_id)
    for target_id in dict.fromkeys(trigger_successors):
        connect(internal_name, names[target_id])

    return {
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveDataErrorExecution": "all",
            "saveDataSuccessExecution": "all",
            "saveExecutionProgress": True,
        },
    }
