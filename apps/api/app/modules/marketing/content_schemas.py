from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.core.schemas import StrictSchema


class ChannelConnectorUpsert(StrictSchema):
    channel: Literal["email", "whatsapp", "sms", "web"]
    provider: str = Field(min_length=2, max_length=80)
    credential_id: UUID | None = None
    sender_reference: str | None = Field(default=None, max_length=180)
    configuration: dict[str, Any] = Field(default_factory=dict)
    status: Literal["draft", "active", "disabled", "error"] = "draft"


class ChannelConnectorResponse(StrictSchema):
    id: UUID
    channel: str
    provider: str
    credential_id: UUID | None
    sender_reference: str | None
    status: str
    configuration: dict[str, Any]
    updated_at: datetime


class ContentCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=180)
    kind: Literal["email", "whatsapp", "sms", "landing_page"]
    subject: str | None = Field(default=None, max_length=240)
    body: str = Field(min_length=1, max_length=200_000)
    ai_generated: bool = False


class ContentVersionCreate(StrictSchema):
    subject: str | None = Field(default=None, max_length=240)
    body: str = Field(min_length=1, max_length=200_000)
    ai_generated: bool = False
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ContentReview(StrictSchema):
    decision: Literal["submit", "approve", "reject"]
    notes: str | None = Field(default=None, max_length=10_000)


class ContentResponse(StrictSchema):
    id: UUID
    name: str
    kind: str
    status: str
    current_version: int
    subject: str | None
    body: str
    ai_generated: bool
    review_status: str
    updated_at: datetime


class LandingPageCreate(StrictSchema):
    content_id: UUID
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,119}$")
    title: str = Field(min_length=2, max_length=180)
    form_schema: dict[str, Any]

    @model_validator(mode="after")
    def validate_form_schema(self) -> LandingPageCreate:
        fields = self.form_schema.get("fields")
        if not isinstance(fields, list) or not fields or len(fields) > 30:
            raise ValueError("O formulário deve possuir entre 1 e 30 campos.")
        names: set[str] = set()
        for field in fields:
            if not isinstance(field, dict):
                raise ValueError("Campo de formulário inválido.")
            name = field.get("name")
            if not isinstance(name, str) or not name.isidentifier() or name in names:
                raise ValueError("Cada campo precisa de nome único e seguro.")
            if field.get("type") not in {"text", "email", "phone", "textarea", "checkbox"}:
                raise ValueError("Tipo de campo não permitido.")
            names.add(name)
        if self.form_schema.get("require_consent") is not True:
            raise ValueError("A coleta pública exige consentimento explícito.")
        return self


class LandingPageResponse(StrictSchema):
    id: UUID
    public_id: UUID
    content_id: UUID
    slug: str
    title: str
    status: str
    form_schema: dict[str, Any]
    public_path: str
    updated_at: datetime


class PublicLandingPageResponse(StrictSchema):
    title: str
    body: str
    form_schema: dict[str, Any]


class PublicFormSubmission(StrictSchema):
    values: dict[str, Any]
    consent_granted: bool


class PublicFormSubmissionResponse(StrictSchema):
    submission_id: UUID
    status: Literal["accepted"]
