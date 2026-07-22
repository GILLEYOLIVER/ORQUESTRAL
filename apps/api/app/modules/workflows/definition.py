from __future__ import annotations

import json
import re
from typing import Any, cast


class WorkflowDefinitionError(ValueError):
    pass


BLOCK_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "type": "trigger.manual",
        "category": "Gatilhos",
        "label": "Inicio manual",
        "description": "Inicia por comando de um usuario autorizado.",
        "required_fields": [],
        "defaults": {},
    },
    {
        "type": "trigger.schedule",
        "category": "Gatilhos",
        "label": "Horario",
        "description": "Executa em um intervalo programado.",
        "required_fields": ["interval_minutes"],
        "defaults": {"interval_minutes": 60},
    },
    {
        "type": "trigger.webhook",
        "category": "Gatilhos",
        "label": "Webhook",
        "description": "Recebe um evento HTTP autorizado.",
        "required_fields": [],
        "defaults": {},
    },
    {
        "type": "trigger.message_received",
        "category": "Gatilhos",
        "label": "Mensagem recebida",
        "description": "Inicia quando uma integracao entrega uma mensagem.",
        "required_fields": ["channel"],
        "defaults": {"channel": "whatsapp"},
    },
    {
        "type": "trigger.contact_created",
        "category": "Gatilhos",
        "label": "Novo contato",
        "description": "Inicia quando um contato e criado.",
        "required_fields": [],
        "defaults": {},
    },
    {
        "type": "trigger.domain_event",
        "category": "Gatilhos",
        "label": "Evento empresarial",
        "description": "Inicia ao receber um evento publicado e validado da empresa.",
        "required_fields": ["event_type", "event_version"],
        "defaults": {"event_type": "contact.created", "event_version": 1, "max_attempts": 8},
    },
    {
        "type": "logic.condition",
        "category": "Logica",
        "label": "Condicao",
        "description": "Divide o fluxo entre verdadeiro e falso.",
        "required_fields": ["expression"],
        "defaults": {"expression": "$json.input != null"},
    },
    {
        "type": "logic.wait",
        "category": "Logica",
        "label": "Espera",
        "description": "Pausa a execucao por um periodo controlado.",
        "required_fields": ["seconds"],
        "defaults": {"seconds": 5},
    },
    {
        "type": "logic.loop",
        "category": "Logica",
        "label": "Repeticao",
        "description": "Repete uma etapa com limite explicito.",
        "required_fields": ["max_iterations"],
        "defaults": {"max_iterations": 10},
    },
    {
        "type": "data.query",
        "category": "Dados",
        "label": "Consulta",
        "description": "Consulta dados por um adaptador autorizado.",
        "required_fields": ["resource"],
        "defaults": {"resource": "contacts"},
    },
    {
        "type": "data.update",
        "category": "Dados",
        "label": "Atualizacao",
        "description": "Atualiza um recurso com campos declarados.",
        "required_fields": ["resource", "fields"],
        "defaults": {"resource": "contacts", "fields": {}},
    },
    {
        "type": "action.email",
        "category": "Acoes",
        "label": "E-mail",
        "description": "Envia e-mail usando uma credencial do cofre.",
        "required_fields": ["credential_id", "recipient", "subject", "on_error"],
        "defaults": {"recipient": "", "subject": "", "credential_id": "", "on_error": "stop"},
    },
    {
        "type": "action.message",
        "category": "Acoes",
        "label": "Mensagem",
        "description": "Envia mensagem por um plugin autorizado.",
        "required_fields": ["credential_id", "recipient", "on_error"],
        "defaults": {"recipient": "", "credential_id": "", "on_error": "stop"},
    },
    {
        "type": "action.agent",
        "category": "Inteligencia",
        "label": "Agente",
        "description": "Solicita uma resposta a um agente da empresa.",
        "required_fields": ["agent_id", "prompt", "on_error"],
        "defaults": {"agent_id": "", "prompt": "", "on_error": "stop"},
    },
    {
        "type": "action.human_approval",
        "category": "Inteligencia",
        "label": "Aprovacao humana",
        "description": "Interrompe ate uma decisao humana registrada.",
        "required_fields": ["approver_role", "on_error"],
        "defaults": {"approver_role": "owner", "on_error": "stop"},
    },
    {
        "type": "action.plugin",
        "category": "Acoes",
        "label": "Plugin",
        "description": "Executa uma acao de plugin habilitado.",
        "required_fields": ["plugin_code", "action", "credential_id", "on_error"],
        "defaults": {"plugin_code": "", "action": "", "credential_id": "", "on_error": "stop"},
    },
    {
        "type": "flow.end",
        "category": "Fluxo",
        "label": "Encerramento",
        "description": "Finaliza a execucao e devolve o resultado.",
        "required_fields": [],
        "defaults": {},
    },
)

BLOCK_BY_TYPE = {item["type"]: item for item in BLOCK_CATALOG}
TRIGGER_TYPES = {item["type"] for item in BLOCK_CATALOG if item["type"].startswith("trigger.")}
ACTION_TYPES = {item["type"] for item in BLOCK_CATALOG if item["type"].startswith("action.")}
SENSITIVE_KEYS = frozenset({"password", "secret", "token", "api_key", "apikey", "authorization"})
EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
DEFAULT_EXECUTION_POLICY: dict[str, Any] = {
    "max_steps": 100,
    "timeout_seconds": 300,
    "concurrency_limit": 1,
    "on_conflict": "reject",
}
DEFAULT_COMPENSATION_POLICY: dict[str, Any] = {
    "enabled": False,
    "mode": "manual",
    "on_status": ["error", "canceled"],
}


def block_catalog() -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], json.loads(json.dumps(BLOCK_CATALOG)))


def execution_policy(definition: dict[str, Any]) -> dict[str, Any]:
    raw = definition.get("execution_policy")
    policy = dict(DEFAULT_EXECUTION_POLICY)
    if isinstance(raw, dict):
        policy.update(raw)
    return policy


def compensation_policy(definition: dict[str, Any]) -> dict[str, Any]:
    raw = definition.get("compensation_policy")
    policy = dict(DEFAULT_COMPENSATION_POLICY)
    if isinstance(raw, dict):
        policy.update(raw)
    return policy


def is_compensation_only(node: dict[str, Any]) -> bool:
    config = node.get("config")
    return isinstance(config, dict) and config.get("compensation_only") is True


def build_compensation_plan(definition: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = [item for item in definition.get("nodes", []) if isinstance(item, dict)]
    by_id = {str(item.get("id")): item for item in nodes}
    plan: list[dict[str, Any]] = []
    for source in nodes:
        config = source.get("config")
        if not isinstance(config, dict) or is_compensation_only(source):
            continue
        binding = config.get("compensation")
        if not isinstance(binding, dict) or binding.get("enabled") is not True:
            continue
        target_id = str(binding.get("action_node_id") or "")
        target = by_id.get(target_id)
        if target is None:
            continue
        plan.append(
            {
                "source_node_id": str(source.get("id")),
                "source_label": str(source.get("label") or source.get("type"))[:160],
                "action_node_id": target_id,
                "action_label": str(target.get("label") or target.get("type"))[:160],
                "status": "pending",
            }
        )
    return plan


def build_default_definition(_webhook_path: str | None = None) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "trigger-manual",
                "type": "trigger.manual",
                "label": "Inicio manual",
                "position": {"x": 80, "y": 180},
                "config": {},
            },
            {
                "id": "flow-end",
                "type": "flow.end",
                "label": "Encerramento",
                "position": {"x": 430, "y": 180},
                "config": {},
            },
        ],
        "connections": [
            {
                "id": "edge-trigger-end",
                "source": "trigger-manual",
                "target": "flow-end",
                "source_handle": "main",
            }
        ],
        "variables": {},
        "execution_policy": dict(DEFAULT_EXECUTION_POLICY),
        "compensation_policy": dict(DEFAULT_COMPENSATION_POLICY),
        "version": 1,
    }


def _issue(severity: str, code: str, message: str, node_id: str | None = None) -> dict[str, Any]:
    return {"severity": severity, "code": code, "message": message, "node_id": node_id}


def _embedded_secret(value: Any, path: tuple[str, ...] = ()) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in SENSITIVE_KEYS and normalized != "credential_id":
                return ".".join((*path, str(key)))
            found = _embedded_secret(item, (*path, str(key)))
            if found:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found = _embedded_secret(item, (*path, str(index)))
            if found:
                return found
    return None


def analyze_definition(definition: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not isinstance(definition, dict):
        return [_issue("error", "invalid_definition", "A definicao deve ser um objeto.")]
    if set(definition) - {
        "nodes",
        "connections",
        "variables",
        "execution_policy",
        "compensation_policy",
        "version",
    }:
        issues.append(
            _issue("error", "unknown_properties", "A definicao contem propriedades nao permitidas.")
        )
    nodes = definition.get("nodes")
    connections = definition.get("connections")
    variables = definition.get("variables")
    version = definition.get("version")
    if not isinstance(nodes, list) or not 2 <= len(nodes) <= 100:
        return [
            *issues,
            _issue("error", "invalid_nodes", "A definicao deve possuir entre 2 e 100 blocos."),
        ]
    if not isinstance(connections, list):
        return [
            *issues,
            _issue("error", "invalid_connections", "As conexoes devem ser uma lista."),
        ]
    if not isinstance(variables, dict) or version != 1:
        issues.append(
            _issue(
                "error",
                "invalid_metadata",
                "Variaveis devem ser um objeto e a versao da definicao deve ser 1.",
            )
        )
    policy = execution_policy(definition)
    policy_ranges = {
        "max_steps": (2, 1000),
        "timeout_seconds": (5, 3600),
        "concurrency_limit": (1, 50),
    }
    if "execution_policy" in definition and not isinstance(
        definition.get("execution_policy"), dict
    ):
        issues.append(
            _issue("error", "invalid_execution_policy", "A politica de execucao e invalida.")
        )
    for field, (minimum, maximum) in policy_ranges.items():
        value = policy.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            issues.append(
                _issue(
                    "error",
                    "invalid_execution_policy",
                    f"{field} deve estar entre {minimum} e {maximum}.",
                )
            )
    if policy.get("on_conflict") != "reject":
        issues.append(
            _issue(
                "error",
                "invalid_execution_policy",
                "Conflitos de concorrencia devem ser rejeitados com seguranca.",
            )
        )
    compensation = compensation_policy(definition)
    if "compensation_policy" in definition and not isinstance(
        definition.get("compensation_policy"), dict
    ):
        issues.append(
            _issue("error", "invalid_compensation_policy", "A politica de compensacao e invalida.")
        )
    if not isinstance(compensation.get("enabled"), bool):
        issues.append(
            _issue(
                "error",
                "invalid_compensation_policy",
                "A ativacao da compensacao deve ser verdadeira ou falsa.",
            )
        )
    if compensation.get("mode") != "manual":
        issues.append(
            _issue(
                "error",
                "invalid_compensation_policy",
                "Somente compensacao manual supervisionada e permitida nesta fase.",
            )
        )
    on_status = compensation.get("on_status")
    if (
        not isinstance(on_status, list)
        or not on_status
        or not all(item in {"error", "canceled"} for item in on_status)
    ):
        issues.append(
            _issue(
                "error",
                "invalid_compensation_policy",
                "Selecione error e/ou canceled para preparar a compensacao.",
            )
        )

    by_id: dict[str, dict[str, Any]] = {}
    compensation_nodes: set[str] = set()
    compensation_links: list[tuple[str, str]] = []
    triggers: set[str] = set()
    endings: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            issues.append(_issue("error", "invalid_node", "Todos os blocos devem ser objetos."))
            continue
        node_id = node.get("id")
        node_type = node.get("type")
        if not isinstance(node_id, str) or not node_id.strip() or node_id in by_id:
            issues.append(
                _issue(
                    "error",
                    "duplicate_node",
                    "Cada bloco deve possuir um identificador unico.",
                    str(node_id or ""),
                )
            )
            continue
        by_id[node_id] = node
        catalog = BLOCK_BY_TYPE.get(str(node_type))
        if catalog is None:
            issues.append(
                _issue(
                    "error",
                    "unsupported_block",
                    f"O bloco {node_type or 'desconhecido'} nao e permitido.",
                    node_id,
                )
            )
            continue
        if node_type in TRIGGER_TYPES:
            triggers.add(node_id)
        if node_type == "flow.end":
            endings.add(node_id)
        config = node.get("config", {})
        if not isinstance(config, dict):
            issues.append(
                _issue(
                    "error",
                    "invalid_config",
                    "A configuracao do bloco deve ser um objeto.",
                    node_id,
                )
            )
            continue
        compensation_only = config.get("compensation_only", False)
        if not isinstance(compensation_only, bool):
            issues.append(
                _issue(
                    "error",
                    "invalid_compensation_block",
                    "A marcacao de bloco compensatorio deve ser verdadeira ou falsa.",
                    node_id,
                )
            )
        elif compensation_only:
            if node_type not in ACTION_TYPES:
                issues.append(
                    _issue(
                        "error",
                        "invalid_compensation_block",
                        "Somente blocos de acao podem ser usados como compensacao.",
                        node_id,
                    )
                )
            compensation_nodes.add(node_id)
        secret_path = _embedded_secret(config)
        if secret_path:
            issues.append(
                _issue(
                    "error",
                    "embedded_secret",
                    "Use apenas referencias do cofre; segredos nao podem ficar no fluxo.",
                    node_id,
                )
            )
        for field in catalog["required_fields"]:
            if field not in config or config[field] in (None, ""):
                issues.append(
                    _issue(
                        "error",
                        "required_field",
                        f"Preencha o campo obrigatorio: {field}.",
                        node_id,
                    )
                )
        if node_type in ACTION_TYPES and config.get("on_error") not in {"stop", "continue"}:
            issues.append(
                _issue(
                    "error",
                    "missing_error_policy",
                    "Defina o tratamento de erro como stop ou continue.",
                    node_id,
                )
            )
        retry = config.get("retry_policy")
        if retry is not None:
            if not isinstance(retry, dict):
                issues.append(
                    _issue(
                        "error",
                        "invalid_retry_policy",
                        "A politica de retentativa do bloco e invalida.",
                        node_id,
                    )
                )
            else:
                enabled = retry.get("enabled", False)
                max_attempts = retry.get("max_attempts", 1)
                wait_seconds = retry.get("wait_seconds", 1)
                if not isinstance(enabled, bool):
                    issues.append(
                        _issue(
                            "error",
                            "invalid_retry_policy",
                            "A ativacao da retentativa deve ser verdadeira ou falsa.",
                            node_id,
                        )
                    )
                if (
                    isinstance(max_attempts, bool)
                    or not isinstance(max_attempts, int)
                    or not 1 <= max_attempts <= 10
                ):
                    issues.append(
                        _issue(
                            "error",
                            "invalid_retry_policy",
                            "As tentativas devem estar entre 1 e 10.",
                            node_id,
                        )
                    )
                if (
                    isinstance(wait_seconds, bool)
                    or not isinstance(wait_seconds, int)
                    or not 1 <= wait_seconds <= 300
                ):
                    issues.append(
                        _issue(
                            "error",
                            "invalid_retry_policy",
                            "A espera entre tentativas deve estar entre 1 e 300 segundos.",
                            node_id,
                        )
                    )
        if config.get("enabled") is False:
            issues.append(
                _issue(
                    "error",
                    "disabled_tool",
                    "O bloco referencia uma ferramenta desativada.",
                    node_id,
                )
            )
        if node_type == "logic.loop":
            loop_maximum = config.get("max_iterations")
            if not isinstance(loop_maximum, int) or loop_maximum < 1:
                issues.append(
                    _issue(
                        "error",
                        "invalid_loop",
                        "A repeticao precisa de um limite positivo.",
                        node_id,
                    )
                )
            elif loop_maximum > 1000:
                issues.append(
                    _issue(
                        "error",
                        "mass_risk",
                        "O limite de repeticao excede 1000 operacoes.",
                        node_id,
                    )
                )
            elif loop_maximum > 100:
                issues.append(
                    _issue(
                        "warning",
                        "mass_risk",
                        "Esta repeticao pode gerar operacoes em massa.",
                        node_id,
                    )
                )
        if node_type == "trigger.domain_event":
            event_type = str(config.get("event_type", ""))
            event_version = config.get("event_version")
            max_attempts = config.get("max_attempts", 8)
            if not EVENT_TYPE_PATTERN.fullmatch(event_type):
                issues.append(
                    _issue(
                        "error",
                        "invalid_event_type",
                        "Use um tipo de evento no formato dominio.acao.",
                        node_id,
                    )
                )
            if (
                isinstance(event_version, bool)
                or not isinstance(event_version, int)
                or not 1 <= event_version <= 1000
            ):
                issues.append(
                    _issue(
                        "error",
                        "invalid_event_version",
                        "A versao do evento deve estar entre 1 e 1000.",
                        node_id,
                    )
                )
            if (
                isinstance(max_attempts, bool)
                or not isinstance(max_attempts, int)
                or not 1 <= max_attempts <= 25
            ):
                issues.append(
                    _issue(
                        "error",
                        "invalid_event_attempts",
                        "As tentativas do evento devem estar entre 1 e 25.",
                        node_id,
                    )
                )
        binding = config.get("compensation")
        if binding is not None:
            if node_type not in ACTION_TYPES or compensation_only:
                issues.append(
                    _issue(
                        "error",
                        "invalid_compensation_binding",
                        "Apenas uma acao operacional pode apontar para uma compensacao.",
                        node_id,
                    )
                )
            elif not isinstance(binding, dict):
                issues.append(
                    _issue(
                        "error",
                        "invalid_compensation_binding",
                        "A vinculacao de compensacao deve ser um objeto.",
                        node_id,
                    )
                )
            else:
                binding_enabled = binding.get("enabled", False)
                action_node_id = binding.get("action_node_id")
                if not isinstance(binding_enabled, bool) or binding.get("mode") != "manual":
                    issues.append(
                        _issue(
                            "error",
                            "invalid_compensation_binding",
                            "A compensacao do bloco deve ser manual e explicitamente ativada.",
                            node_id,
                        )
                    )
                elif binding_enabled:
                    if not compensation.get("enabled"):
                        issues.append(
                            _issue(
                                "error",
                                "compensation_policy_required",
                                "Ative a politica global antes de vincular compensacoes.",
                                node_id,
                            )
                        )
                    if not isinstance(action_node_id, str) or not action_node_id:
                        issues.append(
                            _issue(
                                "error",
                                "invalid_compensation_binding",
                                "Selecione o bloco que descreve a acao compensatoria.",
                                node_id,
                            )
                        )
                    else:
                        compensation_links.append((node_id, action_node_id))
        if node_type in {"action.email", "action.message"} and str(
            config.get("recipient", "")
        ).strip().lower() in {"*", "all", "todos"}:
            issues.append(
                _issue(
                    "error",
                    "mass_recipient",
                    "Destinatarios em massa exigem uma segmentacao explicita.",
                    node_id,
                )
            )

    linked_targets: dict[str, list[str]] = {}
    for source_id, target_id in compensation_links:
        target = by_id.get(target_id)
        if target_id == source_id or target is None:
            issues.append(
                _issue(
                    "error",
                    "invalid_compensation_target",
                    "O bloco compensatorio selecionado nao existe ou aponta para si mesmo.",
                    source_id,
                )
            )
            continue
        if str(target.get("type")) not in ACTION_TYPES or target_id not in compensation_nodes:
            issues.append(
                _issue(
                    "error",
                    "invalid_compensation_target",
                    "O destino deve ser uma acao marcada exclusivamente como compensatoria.",
                    source_id,
                )
            )
            continue
        linked_targets.setdefault(target_id, []).append(source_id)
    for target_id in compensation_nodes:
        sources = linked_targets.get(target_id, [])
        if not sources:
            issues.append(
                _issue(
                    "error",
                    "unbound_compensation_block",
                    "Vincule o bloco compensatorio a uma acao operacional.",
                    target_id,
                )
            )
        elif len(sources) > 1:
            issues.append(
                _issue(
                    "error",
                    "shared_compensation_block",
                    "Cada bloco compensatorio deve atender uma unica acao.",
                    target_id,
                )
            )

    outgoing: dict[str, list[str]] = {node_id: [] for node_id in by_id}
    incoming: dict[str, int] = {node_id: 0 for node_id in by_id}
    edge_keys: set[tuple[str, str, str]] = set()
    for edge in connections:
        if not isinstance(edge, dict):
            issues.append(_issue("error", "invalid_edge", "Todas as conexoes devem ser objetos."))
            continue
        source = edge.get("source")
        target = edge.get("target")
        handle = str(edge.get("source_handle", "main"))
        if (
            source not in by_id
            or target not in by_id
            or source == target
            or source in compensation_nodes
            or target in compensation_nodes
        ):
            issues.append(
                _issue(
                    "error",
                    "invalid_edge",
                    "A definicao possui uma conexao invalida.",
                    str(source or ""),
                )
            )
            continue
        key = (str(source), str(target), handle)
        if key in edge_keys:
            issues.append(
                _issue("warning", "duplicate_edge", "A conexao esta duplicada.", str(source))
            )
            continue
        edge_keys.add(key)
        outgoing[str(source)].append(str(target))
        incoming[str(target)] += 1

    if not triggers:
        issues.append(_issue("error", "missing_trigger", "Inclua ao menos um gatilho."))
    if not endings:
        issues.append(_issue("error", "missing_end", "Inclua ao menos um encerramento."))
    for trigger in triggers:
        if incoming.get(trigger, 0):
            issues.append(
                _issue(
                    "error", "trigger_with_input", "Gatilhos nao podem receber conexoes.", trigger
                )
            )
    for ending in endings:
        if outgoing.get(ending):
            issues.append(
                _issue(
                    "error",
                    "end_with_output",
                    "O encerramento nao pode iniciar outra etapa.",
                    ending,
                )
            )

    reachable: set[str] = set()
    stack = list(triggers)
    while stack:
        current = stack.pop()
        if current in reachable:
            continue
        reachable.add(current)
        stack.extend(outgoing.get(current, []))
    for node_id in by_id:
        if node_id in compensation_nodes:
            continue
        if node_id not in reachable:
            issues.append(
                _issue(
                    "error", "disconnected_node", "O bloco esta desconectado dos gatilhos.", node_id
                )
            )

    visiting: set[str] = set()
    visited: set[str] = set()

    def has_cycle(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in visited:
            return False
        visiting.add(node_id)
        for target in outgoing.get(node_id, []):
            if has_cycle(target):
                return True
        visiting.remove(node_id)
        visited.add(node_id)
        return False

    if any(has_cycle(node_id) for node_id in by_id if node_id not in visited):
        issues.append(
            _issue(
                "error",
                "invalid_cycle",
                "O fluxo possui um ciclo invalido; use o bloco de repeticao com limite.",
            )
        )
    if endings and not any(ending in reachable for ending in endings):
        issues.append(_issue("error", "unreachable_end", "Nenhum encerramento pode ser alcancado."))
    return issues


def validate_definition(definition: dict[str, Any]) -> None:
    errors = [item for item in analyze_definition(definition) if item["severity"] == "error"]
    if errors:
        raise WorkflowDefinitionError(str(errors[0]["message"]))


def _is_legacy_n8n(definition: dict[str, Any]) -> bool:
    nodes = definition.get("nodes")
    return isinstance(definition.get("connections"), dict) or (
        isinstance(nodes, list)
        and any(
            isinstance(node, dict) and str(node.get("type", "")).startswith("n8n-")
            for node in nodes
        )
    )


def prepare_definition(
    definition: dict[str, Any] | None, _webhook_path: str | None = None
) -> dict[str, Any]:
    prepared = (
        json.loads(json.dumps(definition)) if definition is not None else build_default_definition()
    )
    if _is_legacy_n8n(prepared):
        prepared = build_default_definition()
    prepared.setdefault("execution_policy", dict(DEFAULT_EXECUTION_POLICY))
    prepared.setdefault("compensation_policy", dict(DEFAULT_COMPENSATION_POLICY))
    validate_definition(prepared)
    return prepared


def export_definition(definition: dict[str, Any]) -> dict[str, Any]:
    exported = cast(dict[str, Any], json.loads(json.dumps(definition)))
    validate_definition(exported)
    return exported


def compare_definitions(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_nodes = {
        str(node.get("id")): node for node in before.get("nodes", []) if isinstance(node, dict)
    }
    after_nodes = {
        str(node.get("id")): node for node in after.get("nodes", []) if isinstance(node, dict)
    }
    shared = before_nodes.keys() & after_nodes.keys()
    return {
        "added_nodes": sorted(after_nodes.keys() - before_nodes.keys()),
        "removed_nodes": sorted(before_nodes.keys() - after_nodes.keys()),
        "changed_nodes": sorted(
            node_id for node_id in shared if before_nodes[node_id] != after_nodes[node_id]
        ),
        "connections_changed": before.get("connections", []) != after.get("connections", []),
    }


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
        return value[:500] + ("..." if len(value) > 500 else "")
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:500]


def as_summary_object(value: Any) -> dict[str, Any]:
    summary = summarize_payload(value)
    return summary if isinstance(summary, dict) else {"value": summary}
