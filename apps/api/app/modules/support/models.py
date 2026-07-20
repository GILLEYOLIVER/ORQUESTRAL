from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
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
