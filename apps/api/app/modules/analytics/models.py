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


class AnalyticsIndicator(Base):
    __tablename__ = "analytics_indicators"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_analytics_indicators_company_code"),
        CheckConstraint(
            "unit IN ('number','currency','percent','hours','days')",
            name="ck_analytics_indicators_unit",
        ),
        CheckConstraint(
            "direction IN ('higher_better','lower_better','neutral')",
            name="ck_analytics_indicators_direction",
        ),
        Index("ix_analytics_indicators_company_active", "company_id", "active"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(140))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80), default="Geral", server_default="Geral")
    unit: Mapped[str] = mapped_column(String(20), default="number", server_default="number")
    direction: Mapped[str] = mapped_column(
        String(24), default="higher_better", server_default="higher_better"
    )
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AnalyticsMeasurement(Base):
    __tablename__ = "analytics_measurements"
    __table_args__ = (
        UniqueConstraint(
            "indicator_id",
            "period_start",
            "period_end",
            name="uq_analytics_measurements_indicator_period",
        ),
        CheckConstraint("period_end >= period_start", name="ck_analytics_measurements_period"),
        Index("ix_analytics_measurements_company_period", "company_id", "period_end"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    indicator_id: Mapped[UUID] = mapped_column(
        ForeignKey("analytics_indicators.id", ondelete="CASCADE"), index=True
    )
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    source: Mapped[str] = mapped_column(String(80), default="manual", server_default="manual")
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
