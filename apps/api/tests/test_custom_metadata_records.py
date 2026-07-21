from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.modules.metadata.models import MetadataFieldDefinition
from app.modules.metadata.record_service import field_permission_map, normalize_record_values


def _field(
    key: str,
    data_type: str,
    *,
    required: bool = False,
    default_value: object | None = None,
    settings: dict[str, Any] | None = None,
) -> MetadataFieldDefinition:
    return MetadataFieldDefinition(
        id=uuid4(),
        company_id=uuid4(),
        version_id=uuid4(),
        key=key,
        label=key.title(),
        data_type=data_type,
        required=required,
        unique_values=False,
        searchable=False,
        default_value=default_value,
        settings=settings or {},
        position=0,
    )


def test_record_values_are_normalized_from_published_field_contracts() -> None:
    fields = [
        _field("name", "text", required=True),
        _field("amount", "decimal"),
        _field("active", "boolean", default_value=True),
    ]
    normalized, errors = normalize_record_values(fields, {"name": "Contrato", "amount": "1250.50"})
    assert errors == []
    assert normalized == {"name": "Contrato", "amount": "1250.50", "active": True}


def test_record_values_reject_unknown_and_invalid_fields() -> None:
    normalized, errors = normalize_record_values(
        [_field("quantity", "integer", required=True)],
        {"quantity": True, "unexpected": "value"},
    )
    assert normalized == {}
    assert errors == [
        "Campo desconhecido: unexpected.",
        "O campo 'quantity' deve ser inteiro.",
    ]


def test_field_permission_map_uses_only_explicit_contracts() -> None:
    fields = [
        _field("public_name", "text"),
        _field(
            "private_note",
            "text",
            settings={
                "read_permission": "metadata.private.view",
                "write_permission": "metadata.private.update",
            },
        ),
    ]
    assert field_permission_map(fields, "read") == {
        "public_name": frozenset(),
        "private_note": frozenset({"metadata.private.view"}),
    }
    assert field_permission_map(fields, "write")["private_note"] == frozenset(
        {"metadata.private.update"}
    )
