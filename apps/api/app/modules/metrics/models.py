from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MetricDailySummary(Base):
    __tablename__ = "metric_daily_summaries"
    __table_args__ = (
        CheckConstraint("count_value >= 0", name="ck_metric_daily_summaries_count"),
        CheckConstraint("numeric_value >= 0", name="ck_metric_daily_summaries_numeric"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    metric_date: Mapped[date] = mapped_column(Date, index=True)
    module: Mapped[str] = mapped_column(String(40), index=True)
    metric_key: Mapped[str] = mapped_column(String(80), index=True)
    agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    workflow_id: Mapped[UUID | None] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    count_value: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    numeric_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=0, server_default="0")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True)


class MetricAggregationRun(Base):
    __tablename__ = "metric_aggregation_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running','success','error')", name="ck_metric_aggregation_runs_status"),
        CheckConstraint("rows_written >= 0", name="ck_metric_aggregation_runs_rows"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    status: Mapped[str] = mapped_column(String(20), default="running", server_default="running", index=True)
    rows_written: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
