from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AnalyticsMetricDefinition(Base):
    __tablename__ = "analytics_metric_definitions"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "code", name="uq_analytics_metric_definitions_company_code"
        ),
        CheckConstraint(
            "aggregation IN ('count','sum','avg','min','max')",
            name="ck_analytics_metric_definitions_aggregation",
        ),
        Index("ix_analytics_metric_definitions_company_active", "company_id", "active"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    dataset: Mapped[str] = mapped_column(String(80))
    aggregation: Mapped[str] = mapped_column(String(12))
    value_field: Mapped[str | None] = mapped_column(String(80))
    unit: Mapped[str] = mapped_column(String(20), default="number")
    filters: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AnalyticsReportDefinition(Base):
    __tablename__ = "analytics_report_definitions"
    __table_args__ = (
        CheckConstraint(
            "visualization IN ('table','bar','line','pie','kpi')",
            name="ck_analytics_report_definitions_visualization",
        ),
        CheckConstraint(
            "status IN ('draft','published','archived')",
            name="ck_analytics_report_definitions_status",
        ),
        Index("ix_analytics_report_definitions_company_status", "company_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text)
    dataset: Mapped[str] = mapped_column(String(80))
    dimensions: Mapped[list[str]] = mapped_column(JSON, default=list)
    metric_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    filters: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    visualization: Mapped[str] = mapped_column(String(16), default="table")
    status: Mapped[str] = mapped_column(String(16), default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AnalyticsDashboardDefinition(Base):
    __tablename__ = "analytics_dashboard_definitions"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "name", name="uq_analytics_dashboard_definitions_company_name"
        ),
        Index(
            "ix_analytics_dashboard_definitions_company_active",
            "company_id",
            "active",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text)
    layout: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AnalyticsReportRun(Base):
    __tablename__ = "analytics_report_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('completed','failed')",
            name="ck_analytics_report_runs_status",
        ),
        Index("ix_analytics_report_runs_company_created", "company_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    report_id: Mapped[UUID] = mapped_column(
        ForeignKey("analytics_report_definitions.id", ondelete="CASCADE"), index=True
    )
    executed_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(16))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
