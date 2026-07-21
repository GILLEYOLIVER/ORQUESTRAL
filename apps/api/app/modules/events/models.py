from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    event,
    insert,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from app.core.database import Base
from app.core.security import utc_now
from app.modules.authorization.models import AuthorizationAuditEvent


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_events_dispatch", "status", "available_at", "created_at"),
        Index("ix_outbox_events_company_type", "company_id", "event_type", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    correlation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    causation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    classification: Mapped[str] = mapped_column(String(24), nullable=False, default="internal")
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class EventConsumption(Base):
    __tablename__ = "event_consumptions"
    __table_args__ = (
        UniqueConstraint("event_id", "consumer_name", name="uq_event_consumption_consumer"),
        Index("ix_event_consumptions_company_consumer", "company_id", "consumer_name"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("outbox_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    consumer_name: Mapped[str] = mapped_column(String(160), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


@event.listens_for(AuthorizationAuditEvent, "after_insert")
def enqueue_authorization_event(
    _mapper: Mapper[AuthorizationAuditEvent],
    connection: Connection,
    audit_event: AuthorizationAuditEvent,
) -> None:
    """Mirror an authorized business action into the outbox transaction."""
    now = utc_now()
    connection.execute(
        insert(OutboxEvent).values(
            id=uuid4(),
            company_id=audit_event.company_id,
            actor_user_id=audit_event.actor_user_id,
            event_type=audit_event.action,
            event_version=1,
            correlation_id=audit_event.id,
            causation_id=None,
            classification="internal",
            payload={
                "audit_event_id": str(audit_event.id),
                "target_type": audit_event.target_type,
                "target_id": audit_event.target_id,
            },
            status="pending",
            attempt_count=0,
            max_attempts=8,
            available_at=now,
            locked_at=None,
            locked_by=None,
            external_id=None,
            last_error_code=None,
            published_at=None,
            created_at=now,
            updated_at=now,
        )
    )
