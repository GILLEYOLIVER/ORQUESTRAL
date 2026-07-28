from __future__ import annotations

from datetime import datetime, time
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketingContactPolicy(Base):
    __tablename__ = "marketing_contact_policies"
    __table_args__ = (
        CheckConstraint("channel IN ('email','whatsapp','sms','web')", name="ck_marketing_contact_policies_channel"),
        CheckConstraint("daily_limit BETWEEN 1 AND 100 AND weekly_limit BETWEEN 1 AND 500", name="ck_marketing_contact_policies_limits"),
        CheckConstraint("weekly_limit >= daily_limit", name="ck_marketing_contact_policies_limit_order"),
        UniqueConstraint("company_id", "channel", name="uq_marketing_contact_policies_company_channel"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(16), index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Sao_Paulo", server_default="America/Sao_Paulo")
    allowed_weekdays: Mapped[list[int]] = mapped_column(JSONB, default=lambda: [0, 1, 2, 3, 4], server_default=text("'[0,1,2,3,4]'::jsonb"))
    window_start: Mapped[time] = mapped_column(Time, default=time(8), server_default="08:00:00")
    window_end: Mapped[time] = mapped_column(Time, default=time(20), server_default="20:00:00")
    daily_limit: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    weekly_limit: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    updated_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now())


class MarketingDeliveryAttempt(Base):
    __tablename__ = "marketing_delivery_attempts"
    __table_args__ = (
        CheckConstraint("channel IN ('email','whatsapp','sms','web')", name="ck_marketing_delivery_attempts_channel"),
        CheckConstraint("status IN ('reserved','sent','delivered','failed','blocked','cancelled')", name="ck_marketing_delivery_attempts_status"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_marketing_delivery_attempts_idempotency"),
        Index("ix_marketing_delivery_attempts_frequency", "company_id", "contact_id", "channel", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[UUID] = mapped_column(ForeignKey("crm_contacts.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[UUID | None] = mapped_column(ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), index=True)
    journey_id: Mapped[UUID | None] = mapped_column(ForeignKey("marketing_journeys.id", ondelete="SET NULL"), index=True)
    channel: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    reason_code: Mapped[str] = mapped_column(String(64), index=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now())
