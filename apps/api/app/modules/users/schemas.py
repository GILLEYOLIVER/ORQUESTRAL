from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field, model_validator

from app.core.schemas import StrictSchema


class CompanyUserResponse(StrictSchema):
    membership_id: UUID
    user_id: UUID
    name: str
    email: EmailStr
    user_status: str
    membership_status: str
    role_id: UUID | None
    role_name: str | None
    is_owner: bool
    created_at: datetime


class InvitationCreate(StrictSchema):
    email: EmailStr
    name: str = Field(min_length=2, max_length=160)
    role_id: UUID


class InvitationResponse(StrictSchema):
    id: UUID
    email: EmailStr
    expires_at: datetime
    development_token: str | None = Field(
        default=None,
        description="Disponível exclusivamente quando DEVELOPMENT_EXPOSE_TOKENS=true.",
    )


class CompanyUserUpdate(StrictSchema):
    status: Literal["active", "disabled"] | None = None
    role_id: UUID | None = None

    @model_validator(mode="after")
    def require_change(self) -> CompanyUserUpdate:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos uma alteração.")
        if "role_id" in self.model_fields_set and self.role_id is None:
            raise ValueError("O papel é obrigatório.")
        return self
