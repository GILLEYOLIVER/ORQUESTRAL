from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.core.schemas import StrictSchema

CompanyStatus = Literal["active", "suspended", "trial", "cancelled"]


class CompanyCreate(StrictSchema):
    legal_name: str = Field(min_length=2, max_length=200)
    trade_name: str = Field(min_length=2, max_length=200)
    document_number: str = Field(min_length=5, max_length=32)
    slug: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    status: CompanyStatus = "trial"
    timezone: str = Field(default="America/Sao_Paulo", min_length=3, max_length=64)
    language: str = Field(default="pt-BR", min_length=2, max_length=16)

    @field_validator("document_number")
    @classmethod
    def normalize_document(cls, value: str) -> str:
        return "".join(character for character in value if character.isalnum()).upper()


class CompanyUpdate(StrictSchema):
    legal_name: str | None = Field(default=None, min_length=2, max_length=200)
    trade_name: str | None = Field(default=None, min_length=2, max_length=200)
    status: CompanyStatus | None = None
    timezone: str | None = Field(default=None, min_length=3, max_length=64)
    language: str | None = Field(default=None, min_length=2, max_length=16)


class CompanyResponse(StrictSchema):
    id: UUID
    legal_name: str
    trade_name: str
    document_number: str
    slug: str
    status: CompanyStatus
    timezone: str
    language: str
    created_at: datetime
    updated_at: datetime
