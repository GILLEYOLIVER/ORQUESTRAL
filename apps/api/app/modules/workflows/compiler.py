from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from app.modules.workflows.definition import (
    TRIGGER_TYPES,
    WorkflowDefinitionError,
    block_catalog,
    execution_policy,
    is_compensation_only,
    validate_definition,
)

COMPILER_VERSION = "1.1"
MINIMUM_N8N_VERSION = "2.30.6"


class WorkflowCompilerError(WorkflowDefinitionError):
    pass


def _name(node: dict[str, Any]) -> str:
    label = str(node.get("label") or node["type"]).strip()[:90]
    return f"{label} [{str(node['id'])[:12]}]"


def _base_node(node: dict[str, Any]) -> dict[str, Any]:
    position = node.get("position", {})
    native = {
        "id": str(node["id"]),
        "name": _name(node),
        "position": [int(position.get("x", 0)), int(position.get("y", 0))],
        "parameters": {},
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
    }
    config = node.get("config", {})
    retry = config.get("retry_policy", {}) if isinstance(config, dict) else {}
    if isinstance(retry, dict) and retry.get("enabled") is True:
        native.update(
            retryOnFail=True,
            maxTries=int(retry.get("max_attempts", 3)),
            waitBetweenTries=int(retry.get("wait_seconds", 1)) * 1_000,
        )
    return native


def _manual_adapter(node: dict[str, Any], _path: str) -> dict[str, Any]:
    native = _base_node(node)
    native.update(type="n8n-nodes-base.manualTrigger", typeVersion=1)
    return native


def _schedule_adapter(node: dict[str, Any], _path: str) -> dict[str, Any]:
    native = _base_node(node)
    minutes = max(1, int(node.get("config", {}).get("interval_minutes", 60)))
    native.update(
        type="n8n-nodes-base.scheduleTrigger",
        typeVersion=1.2,
        parameters={"rule": {"interval": [{"field": "minutes", "minutesInterval": minutes}]}},
    )
    return native


def _webhook_adapter(node: dict[str, Any], path: str) -> dict[str, Any]:
    native = _base_node(node)
    suffix = str(node["id"]).lower().replace("_", "-")[:32]
    native.update(
        type="n8n-nodes-base.webhook",
        typeVersion=2,
        parameters={
            "httpMethod": "POST",
            "path": f"{path}-{suffix}",
            "responseMode": "lastNode",
            "options": {},
        },
    )
    return native


def _condition_adapter(node: dict[str, Any], _path: str) -> dict[str, Any]:
    native = _base_node(node)
    expression = str(node.get("config", {}).get("expression", "$json.input != null"))
    native.update(
        type="n8n-nodes-base.if",
        typeVersion=2.2,
        parameters={
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                },
                "conditions": [
                    {
                        "id": f"condition-{node['id']}",
                        "leftValue": f"={{{{ {expression} }}}}",
                        "rightValue": True,
                        "operator": {
                            "type": "boolean",
                            "operation": "true",
                            "singleValue": True,
                        },
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
    )
    return native


def _wait_adapter(node: dict[str, Any], _path: str) -> dict[str, Any]:
    native = _base_node(node)
    native.update(
        type="n8n-nodes-base.wait",
        typeVersion=1.1,
        parameters={
            "amount": max(1, int(node.get("config", {}).get("seconds", 5))),
            "unit": "seconds",
        },
    )
    return native


def _end_adapter(node: dict[str, Any], _path: str) -> dict[str, Any]:
    return _base_node(node)


NodeAdapter = Callable[[dict[str, Any], str], dict[str, Any]]
_ADAPTERS: dict[str, NodeAdapter] = {
    "trigger.manual": _manual_adapter,
    "trigger.schedule": _schedule_adapter,
    "trigger.webhook": _webhook_adapter,
    "trigger.message_received": _webhook_adapter,
    "trigger.contact_created": _webhook_adapter,
    "trigger.domain_event": _webhook_adapter,
    "logic.condition": _condition_adapter,
    "logic.wait": _wait_adapter,
    "flow.end": _end_adapter,
}

_NATIVE_TYPES = {
    "trigger.manual": ("n8n-nodes-base.manualTrigger", 1),
    "trigger.schedule": ("n8n-nodes-base.scheduleTrigger", 1.2),
    "trigger.webhook": ("n8n-nodes-base.webhook", 2),
    "trigger.message_received": ("n8n-nodes-base.webhook", 2),
    "trigger.contact_created": ("n8n-nodes-base.webhook", 2),
    "trigger.domain_event": ("n8n-nodes-base.webhook", 2),
    "logic.condition": ("n8n-nodes-base.if", 2.2),
    "logic.wait": ("n8n-nodes-base.wait", 1.1),
    "flow.end": ("n8n-nodes-base.noOp", 1),
}


def compiler_compatibility() -> list[dict[str, Any]]:
    compatibility: list[dict[str, Any]] = []
    for block in block_catalog():
        block_type = str(block["type"])
        native = _NATIVE_TYPES.get(block_type)
        supported = block_type in _ADAPTERS
        compatibility.append(
            {
                "block_type": block_type,
                "supported": supported,
                "compiler_version": COMPILER_VERSION,
                "minimum_n8n_version": MINIMUM_N8N_VERSION if supported else None,
                "n8n_node_type": native[0] if native else None,
                "n8n_type_version": native[1] if native else None,
                "reason": None
                if supported
                else "Adaptador ainda não implementado; publicação bloqueada com segurança.",
            }
        )
    return compatibility


def analyze_compiler_compatibility(definition: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for node in definition.get("nodes", []):
        if not isinstance(node, dict):
            continue
        if is_compensation_only(node):
            continue
        block_type = str(node.get("type", ""))
        if block_type and block_type not in _ADAPTERS:
            issues.append(
                {
                    "severity": "error",
                    "code": "compiler_unsupported_block",
                    "message": (
                        f"O bloco {block_type} ainda não possui adaptador para o motor interno."
                    ),
                    "node_id": str(node.get("id") or "") or None,
                }
            )
    return issues


def _native_node(node: dict[str, Any], internal_webhook_path: str) -> dict[str, Any]:
    block_type = str(node["type"])
    adapter = _ADAPTERS.get(block_type)
    if adapter is None:
        raise WorkflowCompilerError(
            f"O bloco {block_type} ainda não possui adaptador para o motor interno."
        )
    return adapter(node, internal_webhook_path)


def compile_definition(definition: dict[str, Any], *, internal_webhook_path: str) -> dict[str, Any]:
    validate_definition(definition)
    compatibility_issues = analyze_compiler_compatibility(definition)
    if compatibility_issues:
        raise WorkflowCompilerError(str(compatibility_issues[0]["message"]))

    source = json.loads(json.dumps(definition))
    visual_nodes = [
        node
        for node in source["nodes"]
        if isinstance(node, dict) and not is_compensation_only(node)
    ]
    by_id = {str(node["id"]): node for node in visual_nodes}
    names = {node_id: _name(node) for node_id, node in by_id.items()}
    nodes = [_native_node(node, internal_webhook_path) for node in visual_nodes]
    internal_name = "Entrada interna Orkestral"
    min_x = min(int(node.get("position", {}).get("x", 0)) for node in visual_nodes)
    min_y = min(int(node.get("position", {}).get("y", 0)) for node in visual_nodes)
    nodes.append(
        {
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
        }
    )

    connections: dict[str, dict[str, list[list[dict[str, Any]]]]] = {}

    def connect(source_name: str, target_name: str, output_index: int = 0) -> None:
        main = connections.setdefault(source_name, {"main": []})["main"]
        while len(main) <= output_index:
            main.append([])
        main[output_index].append({"node": target_name, "type": "main", "index": 0})

    trigger_successors: list[str] = []
    for edge in source["connections"]:
        source_id = str(edge["source"])
        target_id = str(edge["target"])
        if source_id not in by_id or target_id not in by_id:
            continue
        output_index = 1 if str(edge.get("source_handle", "main")) == "false" else 0
        connect(names[source_id], names[target_id], output_index)
        if str(by_id[source_id]["type"]) in TRIGGER_TYPES:
            trigger_successors.append(target_id)
    for target_id in dict.fromkeys(trigger_successors):
        connect(internal_name, names[target_id])

    policy = execution_policy(definition)
    return {
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveDataErrorExecution": "all",
            "saveDataSuccessExecution": "all",
            "saveExecutionProgress": True,
            "executionTimeout": int(policy["timeout_seconds"]),
        },
    }
