from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketingJourneyVersion(Base):
    __tablename__ = "marketing_journey_versions"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_marketing_journey_versions_version"),
        CheckConstraint("status IN ('published','retired')", name="ck_marketing_journey_versions_status"),
        UniqueConstraint("journey_id", "version", name="uq_marketing_journey_versions_number"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    journey_id: Mapped[UUID] = mapped_column(ForeignKey("marketing_journeys.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="published", server_default="published", index=True)
    definition_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    published_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now())


class MarketingJourneySimulation(Base):
    __tablename__ = "marketing_journey_simulations"
    __table_args__ = (
        CheckConstraint("status IN ('passed','failed')", name="ck_marketing_journey_simulations_status"),
        Index("ix_marketing_journey_simulations_company_journey", "company_id", "journey_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    journey_id: Mapped[UUID] = mapped_column(ForeignKey("marketing_journeys.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    definition_checksum: Mapped[str] = mapped_column(String(64), index=True)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    trace_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    issues_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True)


class MarketingExperimentEvidence(Base):
    __tablename__ = "marketing_experiment_evidence"
    __table_args__ = (
        CheckConstraint("sample_size >= 0", name="ck_marketing_experiment_evidence_sample"),
        UniqueConstraint("experiment_id", "variant_key", name="uq_marketing_experiment_evidence_variant"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    experiment_id: Mapped[UUID] = mapped_column(ForeignKey("marketing_experiments.id", ondelete="CASCADE"), index=True)
    variant_key: Mapped[str] = mapped_column(String(80), index=True)
    sample_size: Mapped[int] = mapped_column(Integer)
    metric_value: Mapped[float] = mapped_column(Numeric(18, 6))
    confidence: Mapped[float] = mapped_column(Numeric(8, 6))
    source_rule: Mapped[str] = mapped_column(String(120))
    source_reference: Mapped[str] = mapped_column(String(240))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now())


class MarketingAgentRecommendation(Base):
    __tablename__ = "marketing_agent_recommendations"
    __table_args__ = (
        CheckConstraint("status IN ('proposed','approved','dismissed')", name="ck_marketing_agent_recommendations_status"),
        CheckConstraint("risk_level IN ('low','medium','high')", name="ck_marketing_agent_recommendations_risk"),
        Index("ix_marketing_agent_recommendations_company_status", "company_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="RESTRICT"), index=True)
    agent_version_id: Mapped[UUID] = mapped_column(ForeignKey("agent_versions.id", ondelete="RESTRICT"), index=True)
    recommendation_type: Mapped[str] = mapped_column(String(80), index=True)
    summary: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    risk_level: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="proposed", server_default="proposed", index=True)
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    decided_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True)
