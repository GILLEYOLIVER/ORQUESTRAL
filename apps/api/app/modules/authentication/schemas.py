from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field

from app.core.schemas import StrictSchema


class LoginRequest(StrictSchema):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class SelectCompanyRequest(StrictSchema):
    company_id: UUID


class ForgotPasswordRequest(StrictSchema):
    email: EmailStr


class ResetPasswordRequest(StrictSchema):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=256)


class AcceptInvitationRequest(StrictSchema):
    token: str = Field(min_length=32, max_length=256)
    name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=256)


class AccessTokenResponse(StrictSchema):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_at: datetime


class AuthSessionResponse(StrictSchema):
    id: UUID
    ip_address: str
    user_agent: str | None
    expires_at: datetime
    last_used_at: datetime
    created_at: datetime
    current: bool


class MessageResponse(StrictSchema):
    message: str
    development_token: str | None = Field(
        default=None,
        description="Disponível exclusivamente quando DEVELOPMENT_EXPOSE_TOKENS=true.",
    )


class UserResponse(StrictSchema):
    id: UUID
    name: str
    email: EmailStr
    status: str
    is_platform_admin: bool
    last_login_at: datetime | None


class CompanySummary(StrictSchema):
    id: UUID
    legal_name: str
    trade_name: str
    slug: str
    status: str
    timezone: str
    language: str


class MembershipResponse(StrictSchema):
    id: UUID
    company: CompanySummary
    role_id: UUID | None
    status: str
    is_owner: bool


class MeResponse(StrictSchema):
    user: UserResponse
    current_company: CompanySummary | None
    memberships: list[MembershipResponse]
    permissions: list[str]
    requires_company_selection: bool
