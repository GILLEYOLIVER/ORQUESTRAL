from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, JsonValue, field_validator, model_validator

from app.core.schemas import StrictSchema

MetadataDataType = Literal[
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
MetadataEntityStatus = Literal["draft", "published", "archived"]
MetadataVersionStatus = Literal["draft", "validated", "published", "retired"]
MetadataComparisonOperator = Literal[
    "equals",
    "not_equals",
    "greater_than",
    "less_than",
    "contains",
    "is_empty",
    "is_not_empty",
]


class MetadataFieldInput(StrictSchema):
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=2, max_length=120)
    data_type: MetadataDataType
    required: bool = False
    unique_values: bool = False
    searchable: bool = False
    default_value: JsonValue | None = None
    settings: dict[str, JsonValue] = Field(default_factory=dict)
    position: int = Field(default=0, ge=0, le=10_000)

    @field_validator("key", "label")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class MetadataEntityCreate(StrictSchema):
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=2, max_length=120)
    plural_label: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2_000)
    fields: list[MetadataFieldInput] = Field(min_length=1, max_length=100)

    @field_validator("key", "label", "plural_label")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def reject_duplicate_fields(self) -> MetadataEntityCreate:
        keys = [field.key for field in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("As chaves dos campos devem ser unicas.")
        return self


class MetadataEntityDraftUpdate(StrictSchema):
    label: str | None = Field(default=None, min_length=2, max_length=120)
    plural_label: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2_000)
    fields: list[MetadataFieldInput] = Field(min_length=1, max_length=100)

    @field_validator("label", "plural_label")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def reject_duplicate_fields(self) -> MetadataEntityDraftUpdate:
        keys = [field.key for field in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("As chaves dos campos devem ser unicas.")
        return self


class MetadataLayoutSectionInput(StrictSchema):
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=2, max_length=120)
    fields: list[str] = Field(min_length=1, max_length=100)
    columns: int = Field(default=2, ge=1, le=3)

    @model_validator(mode="after")
    def reject_duplicate_fields(self) -> MetadataLayoutSectionInput:
        if len(self.fields) != len(set(self.fields)):
            raise ValueError("Uma secao nao pode repetir campos.")
        return self


class MetadataLayoutInput(StrictSchema):
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=2, max_length=120)
    sections: list[MetadataLayoutSectionInput] = Field(min_length=1, max_length=20)
    is_default: bool = False

    @model_validator(mode="after")
    def reject_duplicate_sections(self) -> MetadataLayoutInput:
        keys = [section.key for section in self.sections]
        if len(keys) != len(set(keys)):
            raise ValueError("As chaves das secoes devem ser unicas.")
        return self


class MetadataViewFilterInput(StrictSchema):
    field_key: str = Field(min_length=2, max_length=80)
    operator: MetadataComparisonOperator
    value: JsonValue | None = None


class MetadataViewSortInput(StrictSchema):
    field_key: str = Field(min_length=2, max_length=80)
    direction: Literal["asc", "desc"] = "asc"


class MetadataViewInput(StrictSchema):
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=2, max_length=120)
    columns: list[str] = Field(min_length=1, max_length=30)
    filters: list[MetadataViewFilterInput] = Field(default_factory=list, max_length=20)
    sorting: list[MetadataViewSortInput] = Field(default_factory=list, max_length=5)
    is_default: bool = False

    @model_validator(mode="after")
    def reject_duplicate_columns(self) -> MetadataViewInput:
        if len(self.columns) != len(set(self.columns)):
            raise ValueError("Uma visualizacao nao pode repetir colunas.")
        return self


class MetadataValidationRuleInput(StrictSchema):
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=2, max_length=120)
    field_key: str = Field(min_length=2, max_length=80)
    operator: MetadataComparisonOperator
    comparison_value: JsonValue | None = None
    message: str = Field(min_length=3, max_length=500)
    active: bool = True


class MetadataDesignUpdate(StrictSchema):
    layouts: list[MetadataLayoutInput] = Field(min_length=1, max_length=12)
    views: list[MetadataViewInput] = Field(min_length=1, max_length=12)
    validation_rules: list[MetadataValidationRuleInput] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_unique_defaults_and_keys(self) -> MetadataDesignUpdate:
        for name, items in (("layouts", self.layouts), ("views", self.views)):
            keys = [item.key for item in items]
            if len(keys) != len(set(keys)):
                raise ValueError(f"As chaves de {name} devem ser unicas.")
            if sum(item.is_default for item in items) != 1:
                raise ValueError(f"Defina exatamente um item padrao em {name}.")
        rule_keys = [rule.key for rule in self.validation_rules]
        if len(rule_keys) != len(set(rule_keys)):
            raise ValueError("As chaves das regras devem ser unicas.")
        return self


class MetadataDesignResponse(MetadataDesignUpdate):
    version: int
    version_status: MetadataVersionStatus
    checksum: str


class MetadataFieldResponse(MetadataFieldInput):
    id: UUID


class MetadataEntityVersionResponse(StrictSchema):
    id: UUID
    version: int
    status: MetadataVersionStatus
    schema_checksum: str
    fields: list[MetadataFieldResponse]
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MetadataEntitySummary(StrictSchema):
    id: UUID
    key: str
    label: str
    plural_label: str
    status: MetadataEntityStatus
    current_version: int
    published_version: int | None
    created_at: datetime
    updated_at: datetime


class MetadataEntityDetail(MetadataEntitySummary):
    description: str | None
    version: MetadataEntityVersionResponse


class MetadataValidationResponse(StrictSchema):
    entity_id: UUID
    version: int
    valid: bool
    errors: list[str]
    schema_checksum: str
