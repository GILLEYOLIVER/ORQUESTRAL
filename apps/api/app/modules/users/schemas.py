from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field

from app.core.schemas import StrictSchema


class CompanyUserResponse(StrictSchema):
    membership_id: UUID
    user_id: UUID
    name: str
    email: EmailStr
    user_status: str
    membership_status: str
    role_id: UUID | None
    is_owner: bool
    created_at: datetime


class InvitationCreate(StrictSchema):
    email: EmailStr
    name: str = Field(min_length=2, max_length=160)


class InvitationResponse(StrictSchema):
    id: UUID
    email: EmailStr
    expires_at: datetime
    development_token: str | None = Field(
        default=None,
        description="Disponível exclusivamente quando DEVELOPMENT_EXPOSE_TOKENS=true.",
    )


class CompanyUserUpdate(StrictSchema):
    status: Literal["active", "disabled"]
