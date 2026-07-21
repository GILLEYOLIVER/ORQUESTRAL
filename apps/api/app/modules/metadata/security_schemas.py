from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.core.schemas import StrictSchema

MetadataSubjectType = Literal["user", "role"]
MetadataRecordScope = Literal["all", "owned", "owned_shared"]


class MetadataEntityAccessRuleInput(StrictSchema):
    subject_type: MetadataSubjectType
    subject_id: UUID
    can_view: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    can_export: bool = False
    record_scope: MetadataRecordScope = "owned"


class MetadataEntityAccessRuleResponse(MetadataEntityAccessRuleInput):
    id: UUID


class MetadataFieldAccessRuleInput(StrictSchema):
    field_key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    subject_type: MetadataSubjectType
    subject_id: UUID
    can_view: bool = True
    can_edit: bool = False

    @model_validator(mode="after")
    def editing_requires_visibility(self) -> MetadataFieldAccessRuleInput:
        if self.can_edit and not self.can_view:
            raise ValueError("Um campo editavel tambem precisa estar visivel.")
        return self


class MetadataFieldAccessRuleResponse(MetadataFieldAccessRuleInput):
    id: UUID


class MetadataSecurityConfigurationUpdate(StrictSchema):
    entity_rules: list[MetadataEntityAccessRuleInput] = Field(default_factory=list, max_length=500)
    field_rules: list[MetadataFieldAccessRuleInput] = Field(default_factory=list, max_length=5_000)

    @model_validator(mode="after")
    def reject_duplicate_rules(self) -> MetadataSecurityConfigurationUpdate:
        entity_keys = [(item.subject_type, item.subject_id) for item in self.entity_rules]
        field_keys = [
            (item.field_key, item.subject_type, item.subject_id) for item in self.field_rules
        ]
        if len(entity_keys) != len(set(entity_keys)):
            raise ValueError("Existe mais de uma regra para o mesmo usuario ou papel.")
        if len(field_keys) != len(set(field_keys)):
            raise ValueError("Existe mais de uma regra de campo para o mesmo destinatario.")
        return self


class MetadataSecurityConfigurationResponse(StrictSchema):
    definition_id: UUID
    configured: bool
    entity_rules: list[MetadataEntityAccessRuleResponse]
    field_rules: list[MetadataFieldAccessRuleResponse]


class MetadataRecordShareCreate(StrictSchema):
    subject_type: MetadataSubjectType
    subject_id: UUID
    can_view: bool = True
    can_edit: bool = False

    @model_validator(mode="after")
    def editing_requires_visibility(self) -> MetadataRecordShareCreate:
        if self.can_edit and not self.can_view:
            raise ValueError("O compartilhamento para edicao tambem precisa permitir leitura.")
        if not self.can_view:
            raise ValueError("O compartilhamento precisa permitir ao menos a leitura.")
        return self


class MetadataRecordShareResponse(MetadataRecordShareCreate):
    id: UUID
    record_id: UUID
    created_at: datetime
    updated_at: datetime
