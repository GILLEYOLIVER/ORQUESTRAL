from __future__ import annotations

import pytest

from app.modules.workflows.compiler import compile_definition
from app.modules.workflows.definition import (
    WorkflowDefinitionError,
    analyze_definition,
    as_summary_object,
    block_catalog,
    build_default_definition,
    compare_definitions,
    export_definition,
    prepare_definition,
)
from app.modules.workflows.security import sign_webhook_body, verify_webhook_signature


def test_default_visual_workflow_is_valid_and_neutral() -> None:
    definition = prepare_definition(build_default_definition(), "private-path")
    assert definition["version"] == 1
    assert isinstance(definition["connections"], list)
    assert analyze_definition(definition) == []


def test_catalog_contains_all_master_document_blocks() -> None:
    types = {item["type"] for item in block_catalog()}
    assert len(types) == 16
    assert {"trigger.schedule", "logic.condition", "action.agent", "action.human_approval", "action.plugin", "flow.end"} <= types


def test_compiler_injects_private_webhook_without_changing_source() -> None:
    definition = build_default_definition()
    compiled = compile_definition(definition, internal_webhook_path="never-expose-this")
    assert "never-expose-this" in str(compiled)
    assert "never-expose-this" not in str(definition)
    assert any(node["type"] == "n8n-nodes-base.webhook" for node in compiled["nodes"])


def test_workflow_rejects_disconnected_cycle_and_embedded_secret() -> None:
    disconnected = build_default_definition()
    disconnected["connections"] = []
    assert {item["code"] for item in analyze_definition(disconnected)} >= {"disconnected_node", "unreachable_end"}

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
    after["nodes"].append({"id": "wait", "type": "logic.wait", "label": "Espera", "position": {"x": 300, "y": 300}, "config": {"seconds": 2}})
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
    summary = as_summary_object({"access_token": "sensitive", "message": "x" * 800, "nested": {"password": "hidden"}})
    assert summary["access_token"] == "[protegido]"
    assert summary["nested"] == {"password": "[protegido]"}
    assert len(str(summary["message"])) <= 503
