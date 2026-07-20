from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.core.schemas import StrictSchema

AccountType = Literal["bank", "cash", "payment_gateway"]
EntryType = Literal["income", "expense"]
EntryStatus = Literal["pending", "settled", "cancelled"]


class AccountCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=140)
    account_type: AccountType
    opening_balance: Decimal = Field(default=Decimal("0"), max_digits=16, decimal_places=2)


class AccountUpdate(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=140)
    account_type: AccountType | None = None
    opening_balance: Decimal | None = Field(default=None, max_digits=16, decimal_places=2)
    active: bool | None = None


class AccountResponse(StrictSchema):
    id: UUID
    name: str
    account_type: AccountType
    opening_balance: Decimal
    current_balance: Decimal
    active: bool
    created_at: datetime
    updated_at: datetime


class CategoryCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=120)
    entry_type: EntryType


class CategoryResponse(StrictSchema):
    id: UUID
    name: str
    entry_type: EntryType
    active: bool
    created_at: datetime
    updated_at: datetime


class EntryCreate(StrictSchema):
    description: str = Field(min_length=2, max_length=240)
    notes: str | None = Field(default=None, max_length=10_000)
    entry_type: EntryType
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    due_date: date
    competence_date: date | None = None
    category_id: UUID | None = None
    reference: str | None = Field(default=None, max_length=120)


class EntryUpdate(StrictSchema):
    description: str | None = Field(default=None, min_length=2, max_length=240)
    notes: str | None = Field(default=None, max_length=10_000)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=16, decimal_places=2)
    due_date: date | None = None
    competence_date: date | None = None
    category_id: UUID | None = None
    reference: str | None = Field(default=None, max_length=120)


class EntrySettle(StrictSchema):
    account_id: UUID
    payment_method: str | None = Field(default=None, max_length=60)
    settled_at: datetime | None = None


class EntryResponse(StrictSchema):
    id: UUID
    account_id: UUID | None
    category_id: UUID | None
    description: str
    notes: str | None
    entry_type: EntryType
    status: EntryStatus
    amount: Decimal
    due_date: date
    competence_date: date
    settled_at: datetime | None
    payment_method: str | None
    reference: str | None
    overdue: bool
    created_at: datetime
    updated_at: datetime


class FinanceSummaryResponse(StrictSchema):
    current_balance: Decimal
    receivable_pending: Decimal
    payable_pending: Decimal
    income_month: Decimal
    expense_month: Decimal
    overdue_total: Decimal
    overdue_count: int
