from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field, field_validator, model_validator

from app.core.schemas import StrictSchema

ContactStatus = Literal["lead", "prospect", "customer", "inactive"]
OpportunityStatus = Literal["open", "won", "lost"]
OpportunityActivityType = Literal[
    "note", "call", "email", "meeting", "stage_change", "status_change"
]


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


class CRMPipelineStageCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=120)
    position: int = Field(default=0, ge=0)
    probability: int = Field(default=0, ge=0, le=100)
    color: str = Field(default="#2f6f64", pattern=r"^#[0-9a-fA-F]{6}$")


class CRMPipelineStageUpdate(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    position: int | None = Field(default=None, ge=0)
    probability: int | None = Field(default=None, ge=0, le=100)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")

    @model_validator(mode="after")
    def require_change(self) -> CRMPipelineStageUpdate:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar")
        return self


class CRMPipelineStageResponse(StrictSchema):
    id: UUID
    pipeline_id: UUID
    name: str
    position: int
    probability: int
    color: str
    created_at: datetime
    updated_at: datetime


class CRMPipelineCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=160)
    stages: list[CRMPipelineStageCreate] = Field(min_length=2, max_length=20)


class CRMPipelineResponse(StrictSchema):
    id: UUID
    name: str
    is_default: bool
    stages: list[CRMPipelineStageResponse]
    opportunity_count: int
    open_value: Decimal
    created_at: datetime
    updated_at: datetime


class CRMOpportunityCreate(StrictSchema):
    title: str = Field(min_length=2, max_length=200)
    pipeline_id: UUID
    stage_id: UUID
    contact_id: UUID | None = None
    assigned_user_id: UUID | None = None
    amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=16, decimal_places=2)
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: date | None = None
    source: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=10000)


class CRMOpportunityUpdate(StrictSchema):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    pipeline_id: UUID | None = None
    stage_id: UUID | None = None
    contact_id: UUID | None = None
    assigned_user_id: UUID | None = None
    amount: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: date | None = None
    source: str | None = Field(default=None, max_length=80)
    status: OpportunityStatus | None = None
    lost_reason: str | None = Field(default=None, max_length=240)
    notes: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def require_change(self) -> CRMOpportunityUpdate:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar")
        return self


class CRMOpportunityResponse(StrictSchema):
    id: UUID
    pipeline_id: UUID
    pipeline_name: str
    stage_id: UUID
    stage_name: str
    stage_probability: int
    contact_id: UUID | None
    contact_name: str | None
    assigned_user_id: UUID | None
    title: str
    amount: Decimal
    probability: int | None
    expected_close_date: date | None
    source: str | None
    status: OpportunityStatus
    lost_reason: str | None
    notes: str | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CRMOpportunityActivityCreate(StrictSchema):
    activity_type: OpportunityActivityType = "note"
    subject: str = Field(min_length=2, max_length=200)
    body: str | None = Field(default=None, max_length=10000)
    occurred_at: datetime | None = None


class CRMOpportunityActivityResponse(StrictSchema):
    id: UUID
    opportunity_id: UUID
    contact_id: UUID | None
    actor_user_id: UUID | None
    activity_type: OpportunityActivityType
    subject: str
    body: str | None
    occurred_at: datetime
    created_at: datetime


class CRMCommercialSummary(StrictSchema):
    pipeline_count: int
    open_opportunities: int
    open_value: Decimal
    won_opportunities: int
    lost_opportunities: int
    overdue_opportunities: int
    weighted_forecast: Decimal
