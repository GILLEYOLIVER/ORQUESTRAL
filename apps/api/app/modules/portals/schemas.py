from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.core.schemas import StrictSchema

ALLOWED_PORTAL_MODULES = {
    "analytics",
    "commerce",
    "crm",
    "finance",
    "projects",
    "support",
    "knowledge",
}


class PortalCreate(StrictSchema):
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9-]+$", max_length=80)
    name: str = Field(min_length=2, max_length=180)
    audience: Literal["customer", "partner", "supplier", "employee"]
    allowed_modules: list[str] = Field(default_factory=list, max_length=12)
    branding: dict[str, str] = Field(default_factory=dict)

    @field_validator("allowed_modules")
    @classmethod
    def validate_modules(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or not set(value) <= ALLOWED_PORTAL_MODULES:
            raise ValueError("Lista de módulos do portal inválida.")
        return value

    @field_validator("branding")
    @classmethod
    def validate_branding(cls, value: dict[str, str]) -> dict[str, str]:
        if not set(value) <= {"logo_url", "primary_color", "welcome_text"}:
            raise ValueError("Configuração visual não permitida.")
        return value


class PortalResponse(StrictSchema):
    id: UUID
    code: str
    name: str
    audience: str
    allowed_modules: list[str]
    branding: dict[str, object]
    active: bool
    created_at: datetime


class PortalInviteCreate(StrictSchema):
    user_id: UUID
    expiration_hours: int = Field(default=72, ge=1, le=720)


class PortalInviteResponse(StrictSchema):
    membership_id: UUID
    invitation_id: UUID
    token: str
    expires_at: datetime


class PortalInviteAccept(StrictSchema):
    token: str = Field(min_length=32, max_length=200)


class PortalAccessResponse(StrictSchema):
    portal: PortalResponse
    membership_status: str
