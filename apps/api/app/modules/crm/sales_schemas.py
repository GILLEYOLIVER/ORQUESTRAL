from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.core.schemas import StrictSchema

AccountStatus = Literal["prospect", "customer", "partner", "inactive"]
LeadStatus = Literal["new", "working", "qualified", "converted", "disqualified"]


class CRMAccountCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=180)
    legal_name: str | None = Field(default=None, max_length=200)
    website: str | None = Field(default=None, max_length=240)
    industry: str | None = Field(default=None, max_length=120)
    employee_count: int | None = Field(default=None, ge=0, le=10_000_000)
    annual_revenue: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    status: AccountStatus = "prospect"
    owner_user_id: UUID | None = None


class CRMAccountResponse(CRMAccountCreate):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime


class CRMLeadCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=180)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)
    company_name: str | None = Field(default=None, max_length=180)
    job_title: str | None = Field(default=None, max_length=120)
    source: str | None = Field(default=None, max_length=80)
    owner_user_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=4_000)


class CRMLeadUpdate(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)
    company_name: str | None = Field(default=None, max_length=180)
    job_title: str | None = Field(default=None, max_length=120)
    source: str | None = Field(default=None, max_length=80)
    owner_user_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=4_000)
    status: Literal["new", "working"] | None = None


class CRMLeadResponse(StrictSchema):
    id: UUID
    company_id: UUID
    name: str
    email: str | None
    phone: str | None
    company_name: str | None
    job_title: str | None
    source: str | None
    status: LeadStatus
    score: int
    owner_user_id: UUID | None
    notes: str | None
    qualification_note: str | None
    qualified_at: datetime | None
    converted_at: datetime | None
    converted_account_id: UUID | None
    converted_contact_id: UUID | None
    converted_opportunity_id: UUID | None
    created_at: datetime
    updated_at: datetime


class CRMLeadQualification(StrictSchema):
    decision: Literal["qualified", "disqualified"]
    note: str = Field(min_length=3, max_length=1_000)


class CRMLeadConversionCreate(StrictSchema):
    pipeline_id: UUID
    stage_id: UUID
    account_id: UUID | None = None
    create_account: bool = True
    opportunity_title: str = Field(min_length=2, max_length=200)
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    expected_close_date: date | None = None


class CRMLeadConversionResponse(StrictSchema):
    lead_id: UUID
    account_id: UUID | None
    contact_id: UUID
    opportunity_id: UUID
    status: Literal["converted"]
    idempotent: bool
