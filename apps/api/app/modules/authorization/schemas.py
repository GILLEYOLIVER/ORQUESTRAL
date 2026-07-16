from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.schemas import StrictSchema


class PermissionResponse(StrictSchema):
    id: UUID
    code: str
    module_code: str
    action: str
    description: str


class RoleResponse(StrictSchema):
    id: UUID
    company_id: UUID
    name: str
    description: str | None
    is_system_role: bool
    permission_codes: list[str]
    created_at: datetime
    updated_at: datetime


class RoleCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permission_codes: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Informe um nome com ao menos dois caracteres.")
        return normalized


class RoleUpdate(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permission_codes: list[str] | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Informe um nome com ao menos dois caracteres.")
        return normalized

    @model_validator(mode="after")
    def require_change(self) -> RoleUpdate:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos uma alteração.")
        return self


class AuditEventResponse(StrictSchema):
    id: UUID
    actor_user_id: UUID
    action: str
    target_type: str
    target_id: str
    details: dict[str, Any]
    created_at: datetime
