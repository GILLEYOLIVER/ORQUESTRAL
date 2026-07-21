from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.core.schemas import StrictSchema
from app.modules.metadata.schemas import (
    MetadataFieldInput,
    MetadataFormulaInput,
    MetadataLayoutInput,
    MetadataRecordTypeInput,
    MetadataRelationshipType,
    MetadataValidationRuleInput,
    MetadataViewInput,
)


class MetadataPortableRelationship(StrictSchema):
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=2, max_length=120)
    source_field_key: str = Field(min_length=2, max_length=80)
    target_entity_key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    relationship_type: MetadataRelationshipType = "many_to_one"
    on_delete: Literal["restrict"] = "restrict"


class MetadataPortableDesign(StrictSchema):
    layouts: list[MetadataLayoutInput] = Field(min_length=1, max_length=12)
    views: list[MetadataViewInput] = Field(min_length=1, max_length=12)
    validation_rules: list[MetadataValidationRuleInput] = Field(default_factory=list, max_length=50)
    relationships: list[MetadataPortableRelationship] = Field(default_factory=list, max_length=50)
    formulas: list[MetadataFormulaInput] = Field(default_factory=list, max_length=50)
    record_types: list[MetadataRecordTypeInput] = Field(default_factory=list, max_length=20)


class MetadataPackageDefinition(StrictSchema):
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=2, max_length=120)
    plural_label: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2_000)
    fields: list[MetadataFieldInput] = Field(min_length=1, max_length=100)
    design: MetadataPortableDesign


class MetadataEntityPackage(StrictSchema):
    format_version: Literal["1.0"] = "1.0"
    exported_at: datetime
    definition: MetadataPackageDefinition
    checksum: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")


class MetadataPackageImportRequest(StrictSchema):
    package: MetadataEntityPackage
    key_override: str | None = Field(
        default=None, min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$"
    )
    label_override: str | None = Field(default=None, min_length=2, max_length=120)
    plural_label_override: str | None = Field(default=None, min_length=2, max_length=120)

    @field_validator("key_override", "label_override", "plural_label_override")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None
