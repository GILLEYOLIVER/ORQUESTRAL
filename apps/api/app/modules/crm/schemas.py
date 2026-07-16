from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field, field_validator, model_validator

from app.core.schemas import StrictSchema

ContactStatus = Literal["lead", "prospect", "customer", "inactive"]


class CRMTagResponse(StrictSchema):
    id: UUID
    name: str
    created_at: datetime


class CRMTagCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=80)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Informe uma etiqueta válida.")
        return normalized


class CRMContactCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=64)
    company_name: str | None = Field(default=None, max_length=180)
    job_title: str | None = Field(default=None, max_length=120)
    source: str | None = Field(default=None, max_length=80)
    status: ContactStatus = "lead"
    assigned_user_id: UUID | None = None
    tag_ids: list[UUID] = Field(default_factory=list, max_length=50)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Informe um nome válido.")
        return normalized


class CRMContactUpdate(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=64)
    company_name: str | None = Field(default=None, max_length=180)
    job_title: str | None = Field(default=None, max_length=120)
    source: str | None = Field(default=None, max_length=80)
    status: ContactStatus | None = None
    assigned_user_id: UUID | None = None
    tag_ids: list[UUID] | None = Field(default=None, max_length=50)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Informe um nome válido.")
        return normalized

    @model_validator(mode="after")
    def require_change(self) -> CRMContactUpdate:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos uma alteração.")
        return self


class CRMContactResponse(StrictSchema):
    id: UUID
    name: str
    email: EmailStr | None
    phone: str | None
    company_name: str | None
    job_title: str | None
    source: str | None
    status: ContactStatus
    assigned_user_id: UUID | None
    tags: list[CRMTagResponse]
    created_at: datetime
    updated_at: datetime


class CRMContactPage(StrictSchema):
    items: list[CRMContactResponse]
    total: int
    page: int
    page_size: int
    pages: int
