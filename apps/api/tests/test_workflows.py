from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.workflows.compiler import (
    WorkflowCompilerError,
    compile_definition,
    compiler_compatibility,
)
from app.modules.workflows.definition import (
    WorkflowDefinitionError,
    analyze_definition,
    as_summary_object,
    block_catalog,
    build_compensation_plan,
    build_default_definition,
    compare_definitions,
    compensation_policy,
    export_definition,
    prepare_definition,
)
from app.modules.workflows.security import sign_webhook_body, verify_webhook_signature
from app.modules.workflows.simulation import simulate_definition


def test_default_visual_workflow_is_valid_and_neutral() -> None:
    definition = prepare_definition(build_default_definition(), "private-path")
    assert definition["version"] == 1
    assert isinstance(definition["connections"], list)
    assert analyze_definition(definition) == []


def test_catalog_contains_all_master_document_blocks() -> None:
    types = {item["type"] for item in block_catalog()}
    assert len(types) == 17
    assert {
        "trigger.schedule",
        "trigger.domain_event",
        "logic.condition",
        "action.agent",
        "action.human_approval",
        "action.plugin",
        "flow.end",
    } <= types


def test_compiler_injects_private_webhook_without_changing_source() -> None:
    definition = build_default_definition()
    compiled = compile_definition(definition, internal_webhook_path="never-expose-this")
    assert "never-expose-this" in str(compiled)
    assert "never-expose-this" not in str(definition)
    assert any(node["type"] == "n8n-nodes-base.webhook" for node in compiled["nodes"])


def test_compiler_matches_golden_default_fixture() -> None:
    fixture = Path(__file__).parent / "fixtures" / "workflows" / "basic_compiled.json"
    expected = json.loads(fixture.read_text(encoding="utf-8"))
    assert (
        compile_definition(build_default_definition(), internal_webhook_path="private-entry")
        == expected
    )


def test_compiler_compatibility_covers_catalog_and_rejects_missing_adapter() -> None:
    matrix = compiler_compatibility()
    assert len(matrix) == len(block_catalog()) == 17
    assert {item["block_type"] for item in matrix if item["supported"]} == {
        "trigger.manual",
        "trigger.schedule",
        "trigger.webhook",
        "trigger.message_received",
        "trigger.contact_created",
        "trigger.domain_event",
        "logic.condition",
        "logic.wait",
        "flow.end",
    }
    definition = build_default_definition()
    definition["nodes"].insert(
        1,
        {
            "id": "loop",
            "type": "logic.loop",
            "label": "Repeticao",
            "position": {"x": 250, "y": 180},
            "config": {"max_iterations": 3},
        },
    )
    definition["connections"] = [
        {"id": "first", "source": "trigger-manual", "target": "loop"},
        {"id": "second", "source": "loop", "target": "flow-end"},
    ]
    with pytest.raises(WorkflowCompilerError, match=r"logic\.loop"):
        compile_definition(definition, internal_webhook_path="private")


def test_workflow_rejects_disconnected_cycle_and_embedded_secret() -> None:
    disconnected = build_default_definition()
    disconnected["connections"] = []
    assert {item["code"] for item in analyze_definition(disconnected)} >= {
        "disconnected_node",
        "unreachable_end",
    }

    cycle = build_default_definition()
    cycle["connections"].append({"id": "back", "source": "flow-end", "target": "trigger-manual"})
    assert "invalid_cycle" in {item["code"] for item in analyze_definition(cycle)}

    secret = build_default_definition()
    secret["nodes"][0]["config"] = {"api_key": "hidden"}
    with pytest.raises(WorkflowDefinitionError, match="segredos"):
        prepare_definition(secret, "private")


def test_comparison_tracks_nodes_and_connections() -> None:
    before = build_default_definition()
    after = build_default_definition()
    after["nodes"][1]["label"] = "Fim atualizado"
    after["nodes"].append(
        {
            "id": "wait",
            "type": "logic.wait",
            "label": "Espera",
            "position": {"x": 300, "y": 300},
            "config": {"seconds": 2},
        }
    )
    comparison = compare_definitions(before, after)
    assert comparison["added_nodes"] == ["wait"]
    assert comparison["changed_nodes"] == ["flow-end"]


def test_export_preserves_neutral_definition() -> None:
    definition = build_default_definition()
    assert export_definition(definition) == definition


def test_webhook_signature_is_constant_and_body_bound() -> None:
    body = b'{"event":"contact.created"}'
    signature = sign_webhook_body("strong-secret", body)
    assert verify_webhook_signature("strong-secret", body, signature)
    assert not verify_webhook_signature("strong-secret", body + b" ", signature)
    assert not verify_webhook_signature("wrong-secret", body, signature)


def test_payload_summary_redacts_secrets_and_limits_long_values() -> None:
    summary = as_summary_object(
        {"access_token": "sensitive", "message": "x" * 800, "nested": {"password": "hidden"}}
    )
    assert summary["access_token"] == "[protegido]"
    assert summary["nested"] == {"password": "[protegido]"}
    assert len(str(summary["message"])) <= 503


def test_domain_event_policy_and_simulation_block_external_effects() -> None:
    definition = build_default_definition()
    definition["nodes"][0].update(
        type="trigger.domain_event",
        label="Contato criado",
        config={"event_type": "contact.created", "event_version": 1, "max_attempts": 5},
    )
    definition["nodes"].insert(
        1,
        {
            "id": "send-email",
            "type": "action.email",
            "label": "Avisar comercial",
            "position": {"x": 250, "y": 180},
            "config": {
                "credential_id": "vault-reference",
                "recipient": "comercial@example.test",
                "subject": "Novo contato",
                "on_error": "stop",
            },
        },
    )
    definition["connections"] = [
        {"id": "first", "source": "trigger-manual", "target": "send-email"},
        {"id": "second", "source": "send-email", "target": "flow-end"},
    ]
    result = simulate_definition(definition, {"contact_id": "synthetic"})
    assert result["valid"] is True
    assert result["estimated_steps"] == 3
    assert result["blocked_side_effects"] == 1
    assert {item["status"] for item in result["trace"]} >= {"blocked_effect", "simulated"}
    assert "comercial@example.test" not in str(result["trace"])


def test_domain_event_and_execution_policy_reject_unsafe_values() -> None:
    definition = build_default_definition()
    definition["nodes"][0].update(
        type="trigger.domain_event",
        config={"event_type": "INVALID", "event_version": 0, "max_attempts": 99},
    )
    definition["execution_policy"] = {
        "max_steps": 1,
        "timeout_seconds": 1,
        "concurrency_limit": 0,
        "on_conflict": "queue",
    }
    codes = {item["code"] for item in analyze_definition(definition)}
    assert {"invalid_event_type", "invalid_event_version", "invalid_event_attempts"} <= codes
    assert "invalid_execution_policy" in codes


def test_compensation_policy_is_manual_and_explicit() -> None:
    definition = build_default_definition()
    assert compensation_policy(definition) == {
        "enabled": False,
        "mode": "manual",
        "on_status": ["error", "canceled"],
    }
    definition["compensation_policy"] = {
        "enabled": True,
        "mode": "automatic",
        "on_status": ["success"],
    }
    assert "invalid_compensation_policy" in {
        item["code"] for item in analyze_definition(definition)
    }


def test_retry_policy_is_validated_and_compiled_per_block() -> None:
    definition = build_default_definition()
    definition["nodes"].insert(
        1,
        {
            "id": "wait-retry",
            "type": "logic.wait",
            "label": "Espera resiliente",
            "position": {"x": 250, "y": 180},
            "config": {
                "seconds": 1,
                "retry_policy": {
                    "enabled": True,
                    "max_attempts": 4,
                    "wait_seconds": 3,
                },
            },
        },
    )
    definition["connections"] = [
        {"id": "first", "source": "trigger-manual", "target": "wait-retry"},
        {"id": "second", "source": "wait-retry", "target": "flow-end"},
    ]
    compiled = compile_definition(definition, internal_webhook_path="private")
    wait_node = next(item for item in compiled["nodes"] if item["id"] == "wait-retry")
    assert wait_node["retryOnFail"] is True
    assert wait_node["maxTries"] == 4
    assert wait_node["waitBetweenTries"] == 3_000

    definition["nodes"][1]["config"]["retry_policy"]["max_attempts"] = 99
    assert "invalid_retry_policy" in {item["code"] for item in analyze_definition(definition)}


def test_compensation_is_bound_to_an_exclusive_action_block() -> None:
    definition = build_default_definition()
    definition["compensation_policy"]["enabled"] = True
    definition["nodes"].insert(
        1,
        {
            "id": "send-message",
            "type": "action.message",
            "label": "Enviar mensagem",
            "position": {"x": 240, "y": 180},
            "config": {
                "channel": "whatsapp",
                "credential_id": "vault-reference",
                "recipient": "contact.primary",
                "template": "follow-up",
                "on_error": "stop",
                "compensation": {
                    "enabled": True,
                    "mode": "manual",
                    "action_node_id": "cancel-message",
                },
            },
        },
    )
    definition["nodes"].append(
        {
            "id": "cancel-message",
            "type": "action.message",
            "label": "Comunicar cancelamento",
            "position": {"x": 240, "y": 420},
            "config": {
                "channel": "whatsapp",
                "credential_id": "vault-reference",
                "recipient": "contact.primary",
                "template": "cancel-follow-up",
                "on_error": "stop",
                "compensation_only": True,
            },
        }
    )
    definition["connections"] = [
        {"id": "first", "source": "trigger-manual", "target": "send-message"},
        {"id": "second", "source": "send-message", "target": "flow-end"},
    ]
    assert analyze_definition(definition) == []
    assert build_compensation_plan(definition) == [
        {
            "source_node_id": "send-message",
            "source_label": "Enviar mensagem",
            "action_node_id": "cancel-message",
            "action_label": "Comunicar cancelamento",
            "status": "pending",
        }
    ]
    simulation = simulate_definition(definition, {"contact_id": "synthetic"})
    assert simulation["compensation_plan"] == build_compensation_plan(definition)
    assert all(item["node_id"] != "cancel-message" for item in simulation["trace"])


def test_compensation_rejects_cross_graph_or_shared_targets() -> None:
    definition = build_default_definition()
    definition["compensation_policy"]["enabled"] = True
    for index in range(2):
        definition["nodes"].append(
            {
                "id": f"action-{index}",
                "type": "action.plugin",
                "label": f"Acao {index}",
                "position": {"x": 200 + index * 100, "y": 200},
                "config": {
                    "plugin_code": "synthetic",
                    "action": "execute",
                    "credential_id": "vault-reference",
                    "on_error": "stop",
                    "compensation": {
                        "enabled": True,
                        "mode": "manual",
                        "action_node_id": "rollback",
                    },
                },
            }
        )
    definition["nodes"].append(
        {
            "id": "rollback",
            "type": "action.plugin",
            "label": "Reverter",
            "position": {"x": 400, "y": 400},
            "config": {
                "plugin_code": "synthetic",
                "action": "rollback",
                "credential_id": "vault-reference",
                "on_error": "stop",
                "compensation_only": True,
            },
        }
    )
    definition["connections"] = [
        {"id": "one", "source": "trigger-manual", "target": "action-0"},
        {"id": "two", "source": "action-0", "target": "action-1"},
        {"id": "three", "source": "action-1", "target": "flow-end"},
    ]
    assert "shared_compensation_block" in {item["code"] for item in analyze_definition(definition)}
