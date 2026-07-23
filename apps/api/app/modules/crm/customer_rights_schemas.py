from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RestrictionReason = Literal[
    "accuracy_dispute",
    "legal_request",
    "consent_withdrawn",
    "fraud_review",
    "other_governed_reason",
]


class CustomerCorrectionRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=48)
    company_name: str | None = Field(default=None, max_length=160)
    job_title: str | None = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().casefold()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Informe um e-mail válido.")
        return normalized

    @field_validator("display_name", "name", "phone", "company_name", "job_title")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def require_change(self) -> CustomerCorrectionRequest:
        if not self.model_fields_set:
            raise ValueError("Informe pelo menos um campo para correção.")
        if all(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Campos de correção não podem ser nulos.")
        return self


class CustomerCorrectionResponse(BaseModel):
    profile_id: UUID
    applied_fields: list[str]
    corrected_at: datetime


class CustomerProcessingRestrictionCreate(BaseModel):
    reason_code: RestrictionReason


class CustomerProcessingRestrictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    status: Literal["active", "released"]
    reason_code: RestrictionReason
    enforced_at: datetime
    released_at: datetime | None


class CustomerSubjectProfileExport(BaseModel):
    id: UUID
    display_name: str
    profile_type: str
    lifecycle_status: str
    quality_score: int
    status: str


class CustomerSubjectContactExport(BaseModel):
    id: UUID
    name: str
    email: str | None
    phone: str | None
    company_name: str | None
    job_title: str | None
    status: str


class CustomerSubjectIdentityExport(BaseModel):
    identity_type: str
    display_hint: str
    verified: bool
    created_at: datetime


class CustomerSubjectConsentExport(BaseModel):
    purpose: str
    channel: str
    status: str
    lawful_basis: str
    evidence_available: bool
    captured_at: datetime
    expires_at: datetime | None


class CustomerSubjectActivitySummary(BaseModel):
    support_tickets: int
    opportunities: int
    marketing_attributions: int
    privacy_requests: int


class CustomerSubjectExportResponse(BaseModel):
    export_version: Literal["1.0"] = "1.0"
    generated_at: datetime
    profile: CustomerSubjectProfileExport
    contact: CustomerSubjectContactExport | None
    identities: list[CustomerSubjectIdentityExport]
    consents: list[CustomerSubjectConsentExport]
    activity_summary: CustomerSubjectActivitySummary
    processing_restricted: bool
    integrity_sha256: str


class CustomerRightsSummaryResponse(BaseModel):
    active_restrictions: int
    exports_last_30_days: int
    corrections_last_30_days: int
