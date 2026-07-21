from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'in_progress', 'waiting', 'resolved', 'closed')",
            name="ck_support_tickets_status",
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="ck_support_tickets_priority",
        ),
        CheckConstraint(
            "channel IN ('web', 'email', 'phone', 'whatsapp', 'other')",
            name="ck_support_tickets_channel",
        ),
        CheckConstraint(
            "satisfaction_score IS NULL OR (satisfaction_score >= 1 AND satisfaction_score <= 5)",
            name="ck_support_tickets_satisfaction",
        ),
        Index("ix_support_tickets_company_status_created", "company_id", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    requester_contact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("crm_contacts.id", ondelete="SET NULL"), index=True
    )
    assignee_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    subject: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text())
    status: Mapped[str] = mapped_column(
        String(20), default="open", server_default="open", index=True
    )
    priority: Mapped[str] = mapped_column(
        String(20), default="normal", server_default="normal", index=True
    )
    channel: Mapped[str] = mapped_column(
        String(20), default="web", server_default="web", index=True
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    queue_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("support_queues.id", ondelete="SET NULL"), index=True
    )
    sla_policy_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("support_sla_policies.id", ondelete="SET NULL"), index=True
    )
    first_response_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    resolution_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    first_responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    breached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    satisfaction_score: Mapped[int | None]
    satisfaction_comment: Mapped[str | None] = mapped_column(Text())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class SupportInteraction(Base):
    __tablename__ = "support_interactions"
    __table_args__ = (
        Index(
            "ix_support_interactions_company_ticket_created",
            "company_id",
            "ticket_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("support_tickets.id", ondelete="CASCADE"), index=True
    )
    author_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    message: Mapped[str] = mapped_column(Text())
    is_internal: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )


class SupportQueue(Base):
    __tablename__ = "support_queues"
    __table_args__ = (
        UniqueConstraint("company_id", "key", name="uq_support_queues_company_key"),
        Index("ix_support_queues_company_active", "company_id", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    key: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(String(500))
    color: Mapped[str] = mapped_column(String(20), default="#2f6f64", server_default="#2f6f64")
    is_default: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class SupportSLAPolicy(Base):
    __tablename__ = "support_sla_policies"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_support_sla_company_name"),)

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(500))
    targets: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    business_hours_only: Mapped[bool] = mapped_column(
        Boolean(), default=False, server_default="false"
    )
    is_default: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class SupportTicketEvent(Base):
    __tablename__ = "support_ticket_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('created', 'assigned', 'queue_changed', 'priority_changed', "
            "'status_changed', 'first_response', 'sla_breached', 'satisfaction_received')",
            name="ck_support_ticket_events_type",
        ),
        Index("ix_support_ticket_events_company_ticket", "company_id", "ticket_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("support_tickets.id", ondelete="CASCADE"), index=True
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(500))
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
