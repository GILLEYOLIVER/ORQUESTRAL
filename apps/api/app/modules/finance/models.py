from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FinancialAccount(Base):
    __tablename__ = "financial_accounts"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('bank', 'cash', 'payment_gateway')",
            name="ck_financial_accounts_type",
        ),
        UniqueConstraint("company_id", "name", name="uq_financial_accounts_company_name"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(140), index=True)
    account_type: Mapped[str] = mapped_column(String(30), index=True)
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), default=Decimal("0"), server_default="0"
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class FinancialCategory(Base):
    __tablename__ = "financial_categories"
    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('income', 'expense')",
            name="ck_financial_categories_entry_type",
        ),
        UniqueConstraint("company_id", "entry_type", "name", name="uq_financial_categories_scope"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), index=True)
    entry_type: Mapped[str] = mapped_column(String(20), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class FinancialEntry(Base):
    __tablename__ = "financial_entries"
    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('income', 'expense')",
            name="ck_financial_entries_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'settled', 'cancelled')",
            name="ck_financial_entries_status",
        ),
        CheckConstraint("amount > 0", name="ck_financial_entries_amount"),
        Index("ix_financial_entries_company_due", "company_id", "due_date"),
        Index("ix_financial_entries_company_status", "company_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("financial_accounts.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("financial_categories.id", ondelete="SET NULL"), index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    description: Mapped[str] = mapped_column(String(240), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    entry_type: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    due_date: Mapped[date] = mapped_column(Date, index=True)
    competence_date: Mapped[date] = mapped_column(Date, index=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    payment_method: Mapped[str | None] = mapped_column(String(60))
    reference: Mapped[str | None] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )
