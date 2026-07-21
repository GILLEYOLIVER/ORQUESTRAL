from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.metadata.models import MetadataFieldDefinition
from app.modules.metadata.schemas import (
    MetadataDesignUpdate,
    MetadataEntityCreate,
    MetadataFieldInput,
    MetadataLayoutInput,
    MetadataLayoutSectionInput,
    MetadataValidationRuleInput,
    MetadataViewInput,
)
from app.modules.metadata.service import (
    calculate_design_checksum,
    calculate_schema_checksum,
    evaluate_record_validation_rules,
    validate_design_contracts,
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


def _design(*, rule_field: str = "amount") -> MetadataDesignUpdate:
    return MetadataDesignUpdate(
        layouts=[
            MetadataLayoutInput(
                key="default_layout",
                label="Formulario",
                is_default=True,
                sections=[
                    MetadataLayoutSectionInput(
                        key="main_section",
                        label="Principal",
                        fields=["name", "amount"],
                    )
                ],
            )
        ],
        views=[
            MetadataViewInput(
                key="default_view",
                label="Lista",
                columns=["name", "amount"],
                is_default=True,
            )
        ],
        validation_rules=[
            MetadataValidationRuleInput(
                key="positive_amount",
                label="Valor minimo",
                field_key=rule_field,
                operator="greater_than",
                comparison_value="10",
                message="O valor precisa ser maior que 10.",
            )
        ],
    )


def test_design_checksum_is_stable_and_unknown_fields_are_rejected() -> None:
    design = _design(rule_field="unknown")
    fields = [
        MetadataFieldDefinition(key="name", label="Nome", data_type="text", position=0),
        MetadataFieldDefinition(key="amount", label="Valor", data_type="decimal", position=1),
    ]
    assert calculate_design_checksum(design) == calculate_design_checksum(design)
    assert validate_design_contracts(design, fields) == [
        "A regra 'positive_amount' usa o campo desconhecido 'unknown'."
    ]


def test_validation_rules_use_only_deterministic_operators() -> None:
    rules = _design().validation_rules
    assert evaluate_record_validation_rules(rules, {"amount": "9.90"}) == [
        "O valor precisa ser maior que 10."
    ]
    assert evaluate_record_validation_rules(rules, {"amount": "10.01"}) == []
