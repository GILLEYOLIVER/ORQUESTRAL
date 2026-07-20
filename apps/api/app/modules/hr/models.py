from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class HRDepartment(Base):
    __tablename__ = "hr_departments"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_hr_departments_company_name"),
        UniqueConstraint("company_id", "code", name="uq_hr_departments_company_code"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(140), index=True)
    description: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class HREmployee(Base):
    __tablename__ = "hr_employees"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'on_leave', 'terminated')",
            name="ck_hr_employees_status",
        ),
        UniqueConstraint("company_id", "employee_code", name="uq_hr_employees_company_code"),
        UniqueConstraint("company_id", "work_email", name="uq_hr_employees_company_email"),
        Index("ix_hr_employees_company_status", "company_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("hr_departments.id", ondelete="SET NULL"), index=True
    )
    manager_employee_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="SET NULL"), index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    employee_code: Mapped[str] = mapped_column(String(60), index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    work_email: Mapped[str] = mapped_column(String(320), index=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    position: Mapped[str] = mapped_column(String(140), index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", index=True
    )
    hire_date: Mapped[date] = mapped_column(Date, index=True)
    termination_date: Mapped[date | None] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class HRLeaveRequest(Base):
    __tablename__ = "hr_leave_requests"
    __table_args__ = (
        CheckConstraint(
            "leave_type IN ('vacation', 'sick', 'personal', 'other')",
            name="ck_hr_leave_requests_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_hr_leave_requests_status",
        ),
        CheckConstraint("end_date >= start_date", name="ck_hr_leave_requests_dates"),
        Index("ix_hr_leave_requests_company_status", "company_id", "status"),
        Index("ix_hr_leave_requests_company_period", "company_id", "start_date", "end_date"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="CASCADE"), index=True
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    decided_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    leave_type: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", index=True
    )
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    decision_note: Mapped[str | None] = mapped_column(String(1000))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )
