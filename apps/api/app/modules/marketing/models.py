from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketingCampaign(Base):
    __tablename__ = "marketing_campaigns"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('email', 'whatsapp', 'sms', 'social', 'multi_channel')",
            name="ck_marketing_campaigns_channel",
        ),
        CheckConstraint(
            "status IN ('draft', 'scheduled', 'active', 'paused', 'completed', 'cancelled')",
            name="ck_marketing_campaigns_status",
        ),
        CheckConstraint(
            "budget_cents >= 0 AND spent_cents >= 0",
            name="ck_marketing_campaigns_money",
        ),
        Index("ix_marketing_campaigns_company_status", "company_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(180), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[str | None] = mapped_column(String(500))
    channel: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", index=True
    )
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    budget_cents: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    spent_cents: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class MarketingCampaignContact(Base):
    __tablename__ = "marketing_campaign_contacts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'sent', 'delivered', 'engaged', 'converted', 'failed', 'unsubscribed')",
            name="ck_marketing_campaign_contacts_status",
        ),
        UniqueConstraint(
            "campaign_id", "contact_id", name="uq_marketing_campaign_contacts_campaign_contact"
        ),
        Index("ix_marketing_campaign_contacts_campaign_status", "campaign_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[UUID] = mapped_column(
        ForeignKey("crm_contacts.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="planned", server_default="planned", index=True
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class MarketingJourney(Base):
    __tablename__ = "marketing_journeys"
    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('manual', 'contact_created', 'contact_tagged', 'scheduled')",
            name="ck_marketing_journeys_trigger_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'paused', 'archived')",
            name="ck_marketing_journeys_status",
        ),
        Index("ix_marketing_journeys_company_status", "company_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(180), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    trigger_type: Mapped[str] = mapped_column(
        String(30), default="manual", server_default="manual", index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", index=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class MarketingJourneyStep(Base):
    __tablename__ = "marketing_journey_steps"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('wait', 'email', 'whatsapp', 'task', 'webhook')",
            name="ck_marketing_journey_steps_action_type",
        ),
        CheckConstraint("position >= 0", name="ck_marketing_journey_steps_position"),
        UniqueConstraint(
            "journey_id", "position", name="uq_marketing_journey_steps_journey_position"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    journey_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketing_journeys.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(180))
    action_type: Mapped[str] = mapped_column(String(30), index=True)
    position: Mapped[int] = mapped_column(Integer)
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class MarketingCampaignMetric(Base):
    __tablename__ = "marketing_campaign_metrics"
    __table_args__ = (
        CheckConstraint(
            "impressions >= 0 AND reach >= 0 AND clicks >= 0 AND leads >= 0 "
            "AND conversions >= 0 AND spend_cents >= 0 AND revenue_cents >= 0",
            name="ck_marketing_campaign_metrics_nonnegative",
        ),
        UniqueConstraint(
            "campaign_id",
            "observed_on",
            "channel",
            "variant_key",
            name="uq_marketing_campaign_metric_slice",
        ),
        Index("ix_marketing_campaign_metrics_company_date", "company_id", "observed_on"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), index=True
    )
    observed_on: Mapped[date] = mapped_column(Date, index=True)
    channel: Mapped[str] = mapped_column(String(30), default="multi_channel")
    variant_key: Mapped[str] = mapped_column(String(80), default="all", server_default="all")
    impressions: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reach: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    clicks: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    leads: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    conversions: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    spend_cents: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    revenue_cents: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class MarketingExperiment(Base):
    __tablename__ = "marketing_experiments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'running', 'completed', 'cancelled')",
            name="ck_marketing_experiments_status",
        ),
        CheckConstraint(
            "success_metric IN ('click_rate', 'lead_rate', 'conversion_rate', 'revenue')",
            name="ck_marketing_experiments_metric",
        ),
        Index("ix_marketing_experiments_company_status", "company_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(180))
    hypothesis: Mapped[str] = mapped_column(Text)
    success_metric: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    variants: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    winner_key: Mapped[str | None] = mapped_column(String(80))
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class MarketingAttribution(Base):
    __tablename__ = "marketing_attributions"
    __table_args__ = (
        CheckConstraint("value_cents >= 0", name="ck_marketing_attributions_value"),
        CheckConstraint(
            "touchpoint IN ('first_touch', 'lead_creation', 'influenced', 'last_touch', 'conversion')",
            name="ck_marketing_attributions_touchpoint",
        ),
        Index("ix_marketing_attributions_company_campaign", "company_id", "campaign_id"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("crm_contacts.id", ondelete="SET NULL"), index=True
    )
    opportunity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("crm_opportunities.id", ondelete="SET NULL"), index=True
    )
    touchpoint: Mapped[str] = mapped_column(String(30))
    source: Mapped[str | None] = mapped_column(String(120))
    medium: Mapped[str | None] = mapped_column(String(120))
    value_cents: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
