from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.metadata.schemas import MetadataEntityCreate, MetadataFieldInput
from app.modules.metadata.service import (
    calculate_schema_checksum,
    validate_field_contracts,
)


def _field(key: str, position: int) -> MetadataFieldInput:
    return MetadataFieldInput(
        key=key,
        label=key.title(),
        data_type="text",
        position=position,
    )


def test_entity_contract_rejects_duplicate_field_keys() -> None:
    with pytest.raises(ValidationError):
        MetadataEntityCreate(
            key="asset",
            label="Ativo",
            plural_label="Ativos",
            fields=[_field("name", 0), _field("name", 1)],
        )


def test_schema_checksum_is_stable_independent_of_input_order() -> None:
    first = [_field("name", 0), _field("category", 1)]
    second = list(reversed(first))
    assert calculate_schema_checksum(first) == calculate_schema_checksum(second)


def test_reserved_fields_are_rejected_by_business_validation() -> None:
    errors = validate_field_contracts([_field("company_id", 0)])
    assert errors == ["Campos reservados: company_id."]


def test_required_boolean_needs_explicit_default() -> None:
    field = MetadataFieldInput(
        key="active",
        label="Ativo",
        data_type="boolean",
        required=True,
    )
    assert validate_field_contracts([field]) == [
        "O campo booleano obrigatorio 'active' precisa de valor padrao."
    ]
