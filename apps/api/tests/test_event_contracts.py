from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.events.operations_schemas import EventContractCreate, EventSubscriptionCreate
from app.modules.events.operations_service import backward_compatibility_errors, validate_payload


def _schema(*, required: list[str] | None = None) -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "record_id": {"type": "string"},
            "amount": {"type": "number"},
        },
        "required": required or ["record_id"],
        "additionalProperties": False,
    }


def test_contract_schema_accepts_a_bounded_object_contract() -> None:
    contract = EventContractCreate(
        event_type="contact.created",
        version=1,
        payload_schema=_schema(),
    )
    assert contract.payload_schema["type"] == "object"


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "array", "properties": {}},
        {"type": "object", "properties": {}, "required": ["missing"]},
        {"type": "object", "properties": {}, "$ref": "https://example.com/schema"},
    ],
)
def test_contract_schema_rejects_unsafe_or_ambiguous_shapes(schema: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EventContractCreate(event_type="contact.created", version=1, payload_schema=schema)


def test_payload_validation_enforces_required_types_and_extra_fields() -> None:
    assert validate_payload({"record_id": "abc", "amount": 12.5}, _schema()) == []
    errors = validate_payload({"amount": "12", "unexpected": True}, _schema())
    assert "Campo obrigatorio ausente: record_id." in errors
    assert "Tipo invalido para amount." in errors
    assert "Campo nao previsto no contrato: unexpected." in errors


def test_backward_contract_rejects_new_required_fields_and_type_changes() -> None:
    current = _schema(required=["record_id", "amount"])
    current["properties"] = {
        "record_id": {"type": "integer"},
        "amount": {"type": "number"},
    }
    errors = backward_compatibility_errors(_schema(), current)
    assert "Novo campo obrigatorio quebra consumidores anteriores: amount." in errors
    assert "Tipo alterado: record_id." in errors


def test_workflow_subscription_requires_a_workflow_binding() -> None:
    with pytest.raises(ValidationError, match="Selecione uma automacao"):
        EventSubscriptionCreate(
            name="Atualizar pipeline",
            consumer_name="sales.pipeline-updater",
            event_type="opportunity.stage_changed",
            delivery_mode="workflow",
        )
