from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.core.schemas import StrictSchema

EmployeeStatus = Literal["active", "on_leave", "terminated"]
LeaveType = Literal["vacation", "sick", "personal", "other"]
LeaveStatus = Literal["pending", "approved", "rejected", "cancelled"]


class DepartmentCreate(StrictSchema):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=2, max_length=140)
    description: str | None = Field(default=None, max_length=500)


class DepartmentUpdate(StrictSchema):
    code: str | None = Field(default=None, min_length=1, max_length=40)
    name: str | None = Field(default=None, min_length=2, max_length=140)
    description: str | None = Field(default=None, max_length=500)
    active: bool | None = None


class DepartmentResponse(StrictSchema):
    id: UUID
    code: str
    name: str
    description: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


class EmployeeCreate(StrictSchema):
    employee_code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=2, max_length=180)
    work_email: str = Field(min_length=5, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    position: str = Field(min_length=2, max_length=140)
    department_id: UUID | None = None
    manager_employee_id: UUID | None = None
    hire_date: date


class EmployeeUpdate(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    work_email: str | None = Field(default=None, min_length=5, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    position: str | None = Field(default=None, min_length=2, max_length=140)
    department_id: UUID | None = None
    manager_employee_id: UUID | None = None
    status: EmployeeStatus | None = None
    termination_date: date | None = None


class EmployeeResponse(StrictSchema):
    id: UUID
    employee_code: str
    name: str
    work_email: str
    phone: str | None
    position: str
    department_id: UUID | None
    manager_employee_id: UUID | None
    status: EmployeeStatus
    hire_date: date
    termination_date: date | None
    created_at: datetime
    updated_at: datetime


class LeaveRequestCreate(StrictSchema):
    employee_id: UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=10_000)

    @model_validator(mode="after")
    def validate_dates(self) -> LeaveRequestCreate:
        if self.end_date < self.start_date:
            raise ValueError("O fim do afastamento deve ser igual ou posterior ao inicio.")
        return self


class LeaveDecision(StrictSchema):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


class LeaveRequestResponse(StrictSchema):
    id: UUID
    employee_id: UUID
    employee_name: str
    leave_type: LeaveType
    status: LeaveStatus
    start_date: date
    end_date: date
    day_count: int
    reason: str | None
    decision_note: str | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class HRSummaryResponse(StrictSchema):
    employees_active: int
    employees_on_leave: int
    pending_requests: int
    departments_active: int
