from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    event,
    insert,
    text,
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


class EventContract(Base):
    __tablename__ = "event_contracts"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "event_type", "version", name="uq_event_contract_company_type_version"
        ),
        CheckConstraint("version >= 1", name="ck_event_contract_version"),
        CheckConstraint(
            "status IN ('draft', 'published', 'retired')", name="ck_event_contract_status"
        ),
        CheckConstraint(
            "classification IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_event_contract_classification",
        ),
        CheckConstraint(
            "compatibility_mode IN ('strict', 'backward')",
            name="ck_event_contract_compatibility",
        ),
        Index("ix_event_contract_company_type_status", "company_id", "event_type", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    classification: Mapped[str] = mapped_column(String(24), nullable=False, default="internal")
    compatibility_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="backward")
    payload_schema: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class EventSubscription(Base):
    __tablename__ = "event_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "consumer_name", "event_type", name="uq_event_subscription_consumer_type"
        ),
        CheckConstraint("min_version >= 1", name="ck_event_subscription_min_version"),
        CheckConstraint(
            "max_version IS NULL OR max_version >= min_version",
            name="ck_event_subscription_version_range",
        ),
        CheckConstraint(
            "delivery_mode IN ('ledger', 'workflow')", name="ck_event_subscription_delivery_mode"
        ),
        CheckConstraint(
            "(delivery_mode = 'workflow' AND workflow_id IS NOT NULL) OR "
            "(delivery_mode = 'ledger' AND workflow_id IS NULL)",
            name="ck_event_subscription_workflow_binding",
        ),
        CheckConstraint("max_attempts BETWEEN 1 AND 25", name="ck_event_subscription_max_attempts"),
        Index("ix_event_subscription_match", "company_id", "event_type", "active"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    consumer_name: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    min_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="ledger")
    workflow_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    created_by_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class EventDelivery(Base):
    __tablename__ = "event_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "subscription_id", name="uq_event_delivery_event_subscription"
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'succeeded', 'failed', 'dead_letter')",
            name="ck_event_delivery_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_event_delivery_attempts"),
        CheckConstraint("max_attempts BETWEEN 1 AND 25", name="ck_event_delivery_max_attempts"),
        CheckConstraint("replay_count >= 0", name="ck_event_delivery_replay_count"),
        Index("ix_event_delivery_dispatch", "status", "available_at", "locked_at"),
        Index("ix_event_delivery_company_status", "company_id", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
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
    subscription_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("event_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replay_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
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
