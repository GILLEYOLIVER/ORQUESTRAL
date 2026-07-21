from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from pydantic import JsonValue

from app.modules.metadata.schemas import MetadataComparisonOperator, MetadataViewInput

MetadataFieldType = Literal[
    "text",
    "long_text",
    "integer",
    "decimal",
    "boolean",
    "date",
    "datetime",
    "email",
    "phone",
    "url",
    "uuid",
    "json",
]

TEXT_TYPES = frozenset({"text", "long_text", "email", "phone", "url"})
ORDERED_TYPES = frozenset({"integer", "decimal", "date", "datetime"})
SCALAR_TYPES = frozenset(TEXT_TYPES | ORDERED_TYPES | {"boolean", "uuid"})
VALUELESS_OPERATORS = frozenset({"is_empty", "is_not_empty"})


@dataclass(frozen=True, slots=True)
class MetadataRecordFilterSpec:
    field_key: str
    data_type: MetadataFieldType
    operator: MetadataComparisonOperator
    value: JsonValue | None


@dataclass(frozen=True, slots=True)
class MetadataRecordSortSpec:
    field_key: str
    data_type: MetadataFieldType
    direction: Literal["asc", "desc"]


def validate_view_contract(
    view: MetadataViewInput,
    field_types: Mapping[str, str],
) -> list[str]:
    errors: list[str] = []
    for filter_item in view.filters:
        data_type = field_types.get(filter_item.field_key)
        if data_type is None:
            continue
        if data_type not in SCALAR_TYPES:
            errors.append(
                f"A visualizacao '{view.key}' nao pode filtrar o campo estruturado "
                f"'{filter_item.field_key}'."
            )
            continue
        if filter_item.operator == "contains" and data_type not in TEXT_TYPES:
            errors.append(f"O filtro 'contains' da visualizacao '{view.key}' exige campo textual.")
        if filter_item.operator in {"greater_than", "less_than"} and data_type not in ORDERED_TYPES:
            errors.append(f"O filtro de ordem da visualizacao '{view.key}' exige numero ou data.")
        if filter_item.operator in VALUELESS_OPERATORS and filter_item.value is not None:
            errors.append(
                f"O filtro '{filter_item.operator}' da visualizacao '{view.key}' nao aceita valor."
            )
        if filter_item.operator not in VALUELESS_OPERATORS and filter_item.value is None:
            errors.append(
                f"O filtro '{filter_item.operator}' da visualizacao '{view.key}' exige valor."
            )

    sort_fields = [item.field_key for item in view.sorting]
    if len(sort_fields) != len(set(sort_fields)):
        errors.append(f"A visualizacao '{view.key}' nao pode repetir campos de ordenacao.")
    for sort_item in view.sorting:
        data_type = field_types.get(sort_item.field_key)
        if data_type is not None and data_type not in SCALAR_TYPES:
            errors.append(
                f"A visualizacao '{view.key}' nao pode ordenar o campo estruturado "
                f"'{sort_item.field_key}'."
            )
    return errors
