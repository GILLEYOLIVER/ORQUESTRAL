from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, JsonValue, model_validator

from app.core.schemas import StrictSchema


class MetadataRecordCreate(StrictSchema):
    values: dict[str, JsonValue] = Field(min_length=1, max_length=200)
    record_type_key: str | None = Field(default=None, min_length=2, max_length=80)
    idempotency_key: UUID | None = None


class MetadataRecordUpdate(StrictSchema):
    values: dict[str, JsonValue] = Field(min_length=1, max_length=200)
    record_type_key: str | None = Field(default=None, min_length=2, max_length=80)
    expected_version: int = Field(ge=1)

    @model_validator(mode="after")
    def require_values(self) -> MetadataRecordUpdate:
        if not self.values:
            raise ValueError("Informe ao menos um valor para atualizar.")
        return self


class MetadataRecordResponse(StrictSchema):
    id: UUID
    definition_id: UUID
    schema_version: int
    record_type_key: str | None
    values: dict[str, JsonValue]
    masked_fields: list[str]
    record_version: int
    created_at: datetime
    updated_at: datetime


class MetadataRecordPage(StrictSchema):
    items: list[MetadataRecordResponse]
    total: int
    page: int
    page_size: int
    pages: int
