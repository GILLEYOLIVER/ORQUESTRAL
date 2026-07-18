from __future__ import annotations

import json
from typing import Any
from uuid import uuid4


class WorkflowDefinitionError(ValueError):
    pass


ALLOWED_NODE_TYPES = frozenset(
    {
        "n8n-nodes-base.webhook",
        "n8n-nodes-base.respondToWebhook",
        "n8n-nodes-base.set",
        "n8n-nodes-base.if",
        "n8n-nodes-base.noOp",
        "n8n-nodes-base.wait",
    }
)
SENSITIVE_KEYS = ("password", "secret", "token", "api_key", "apikey", "authorization")
WEBHOOK_PATH_PLACEHOLDER = "__ORKESTRAL_WEBHOOK_PATH__"


def build_default_definition(webhook_path: str) -> dict[str, Any]:
    entry_name = "Entrada Orkestral"
    response_name = "Resposta Orkestral"
    return {
        "nodes": [
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": webhook_path,
                    "responseMode": "responseNode",
                    "options": {},
                },
                "id": str(uuid4()),
                "name": entry_name,
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [0, 0],
            },
            {
                "parameters": {
                    "respondWith": "json",
                    "responseBody": "={{ { ok: true, company_id: $json.body.company_id, workflow_id: $json.body.workflow_id, execution_id: $json.body.execution_id, input: $json.body.input } }}",
                    "options": {},
                },
                "id": str(uuid4()),
                "name": response_name,
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1.4,
                "position": [280, 0],
            },
        ],
        "connections": {
            entry_name: {
                "main": [[{"node": response_name, "type": "main", "index": 0}]]
            }
        },
        "settings": {
            "executionOrder": "v1",
            "saveDataErrorExecution": "all",
            "saveDataSuccessExecution": "all",
            "saveExecutionProgress": True,
        },
    }


def validate_definition(definition: dict[str, Any]) -> None:
    if set(definition) - {"nodes", "connections", "settings", "staticData", "pinData"}:
        raise WorkflowDefinitionError("A definição contém propriedades não permitidas.")
    nodes = definition.get("nodes")
    connections = definition.get("connections")
    settings = definition.get("settings")
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 100:
        raise WorkflowDefinitionError("A definição deve possuir entre 1 e 100 blocos.")
    if not isinstance(connections, dict) or not isinstance(settings, dict):
        raise WorkflowDefinitionError("Conexões e configurações devem ser objetos válidos.")
    webhook_count = 0
    names: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise WorkflowDefinitionError("Todos os blocos devem ser objetos válidos.")
        node_type = node.get("type")
        name = node.get("name")
        if node_type not in ALLOWED_NODE_TYPES:
            raise WorkflowDefinitionError(f"O bloco {node_type or 'desconhecido'} não é permitido.")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise WorkflowDefinitionError("Os blocos devem possuir nomes únicos.")
        names.add(name)
        if "credentials" in node:
            raise WorkflowDefinitionError("Importe credenciais pelo cofre, não pela definição.")
        if node_type == "n8n-nodes-base.webhook":
            webhook_count += 1
    if webhook_count != 1:
        raise WorkflowDefinitionError("A automação deve possuir exatamente uma entrada por webhook.")
    for source, outputs in connections.items():
        if source not in names or not isinstance(outputs, dict):
            raise WorkflowDefinitionError("A definição possui uma conexão inválida.")


def prepare_definition(
    definition: dict[str, Any] | None, webhook_path: str
) -> dict[str, Any]:
    prepared = json.loads(json.dumps(definition)) if definition is not None else build_default_definition(webhook_path)
    nodes = prepared.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if isinstance(node, dict) and node.get("type") == "n8n-nodes-base.webhook":
                parameters = node.setdefault("parameters", {})
                if isinstance(parameters, dict):
                    parameters["path"] = webhook_path
                    parameters["httpMethod"] = "POST"
                    parameters["responseMode"] = "responseNode"
    validate_definition(prepared)
    return prepared


def export_definition(definition: dict[str, Any]) -> dict[str, Any]:
    exported = json.loads(json.dumps(definition))
    for node in exported.get("nodes", []):
        if isinstance(node, dict) and node.get("type") == "n8n-nodes-base.webhook":
            parameters = node.get("parameters")
            if isinstance(parameters, dict):
                parameters["path"] = WEBHOOK_PATH_PLACEHOLDER
    return exported


def summarize_payload(value: Any, *, depth: int = 0) -> Any:
    if depth >= 5:
        return "[limite de profundidade]"
    if isinstance(value, dict):
        summary: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 50:
                summary["_truncated"] = True
                break
            normalized = str(key).lower().replace("-", "_")
            summary[str(key)[:100]] = (
                "[protegido]"
                if any(marker in normalized for marker in SENSITIVE_KEYS)
                else summarize_payload(item, depth=depth + 1)
            )
        return summary
    if isinstance(value, list):
        items = [summarize_payload(item, depth=depth + 1) for item in value[:50]]
        if len(value) > 50:
            items.append("[itens adicionais omitidos]")
        return items
    if isinstance(value, str):
        return value[:500] + ("…" if len(value) > 500 else "")
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:500]


def as_summary_object(value: Any) -> dict[str, Any]:
    summary = summarize_payload(value)
    return summary if isinstance(summary, dict) else {"value": summary}
