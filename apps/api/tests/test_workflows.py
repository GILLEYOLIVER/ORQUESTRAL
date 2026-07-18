from __future__ import annotations

import pytest

from app.modules.workflows.definition import (
    WorkflowDefinitionError,
    as_summary_object,
    build_default_definition,
    export_definition,
    prepare_definition,
)
from app.modules.workflows.security import sign_webhook_body, verify_webhook_signature


def test_default_workflow_has_single_private_webhook() -> None:
    definition = build_default_definition("private-path")

    prepared = prepare_definition(definition, "rotated-path")

    webhook = next(node for node in prepared["nodes"] if node["type"] == "n8n-nodes-base.webhook")
    assert webhook["parameters"]["path"] == "rotated-path"


def test_workflow_rejects_dangerous_nodes_and_embedded_credentials() -> None:
    dangerous = build_default_definition("private")
    dangerous["nodes"][0]["type"] = "n8n-nodes-base.executeCommand"
    with pytest.raises(WorkflowDefinitionError, match="não é permitido"):
        prepare_definition(dangerous, "private")

    credentials = build_default_definition("private")
    credentials["nodes"][0]["credentials"] = {"httpHeaderAuth": {"id": "secret"}}
    with pytest.raises(WorkflowDefinitionError, match="cofre"):
        prepare_definition(credentials, "private")


def test_export_removes_internal_webhook_path() -> None:
    exported = export_definition(build_default_definition("never-expose-this"))

    assert "never-expose-this" not in str(exported)
    assert "__ORKESTRAL_WEBHOOK_PATH__" in str(exported)


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
    assert len(str(summary["message"])) <= 501
