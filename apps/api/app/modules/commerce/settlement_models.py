from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CommercePaymentIntent(Base):
    __tablename__ = "commerce_payment_intents"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "idempotency_key",
            name="uq_commerce_payment_intents_company_idempotency",
        ),
        UniqueConstraint(
            "company_id",
            "provider",
            "provider_reference",
            name="uq_commerce_payment_intents_provider_reference",
        ),
        CheckConstraint("amount > 0", name="ck_commerce_payment_intents_amount"),
        CheckConstraint(
            "status IN ('pending', 'captured', 'failed', 'cancelled', "
            "'refund_pending', 'partially_refunded', 'refunded')",
            name="ck_commerce_payment_intents_status",
        ),
        Index("ix_commerce_payment_intents_company_order", "company_id", "order_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("commerce_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_reference: Mapped[str] = mapped_column(String(180), nullable=False)
    method_type: Mapped[str] = mapped_column(String(40), nullable=False)
    method_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CommercePaymentEvent(Base):
    __tablename__ = "commerce_payment_events"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_commerce_payment_events_provider_event",
        ),
        Index(
            "ix_commerce_payment_events_company_intent",
            "company_id",
            "payment_intent_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_intent_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("commerce_payment_intents.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(180), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CommerceReturn(Base):
    __tablename__ = "commerce_returns"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "idempotency_key",
            name="uq_commerce_returns_company_idempotency",
        ),
        CheckConstraint(
            "status IN ('requested', 'received', 'rejected', 'cancelled')",
            name="ck_commerce_returns_status",
        ),
        CheckConstraint(
            "refund_amount >= 0", name="ck_commerce_returns_refund_amount"
        ),
        Index("ix_commerce_returns_company_order", "company_id", "order_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("commerce_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    stock_location_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inventory_locations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="requested")
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    resolution: Mapped[str | None] = mapped_column(String(24), nullable=True)
    refund_amount: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, default=Decimal("0")
    )
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    received_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CommerceReturnItem(Base):
    __tablename__ = "commerce_return_items"
    __table_args__ = (
        UniqueConstraint(
            "return_id", "order_item_id", name="uq_commerce_return_items_line"
        ),
        CheckConstraint("quantity > 0", name="ck_commerce_return_items_quantity"),
        CheckConstraint(
            "line_refund >= 0", name="ck_commerce_return_items_refund"
        ),
        Index(
            "ix_commerce_return_items_company_return", "company_id", "return_id"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    return_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("commerce_returns.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("commerce_order_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    line_refund: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CommerceCustomerCredit(Base):
    __tablename__ = "commerce_customer_credits"
    __table_args__ = (
        UniqueConstraint("return_id", name="uq_commerce_customer_credits_return"),
        CheckConstraint("amount > 0", name="ck_commerce_customer_credits_amount"),
        CheckConstraint(
            "status IN ('issued', 'refund_pending', 'applied', 'refunded', 'void')",
            name="ck_commerce_customer_credits_status",
        ),
        Index(
            "ix_commerce_customer_credits_company_order", "company_id", "order_id"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("commerce_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    return_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("commerce_returns.id", ondelete="RESTRICT"),
        nullable=False,
    )
    financial_entry_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("financial_entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CommerceCommission(Base):
    __tablename__ = "commerce_commissions"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "idempotency_key",
            name="uq_commerce_commissions_company_idempotency",
        ),
        CheckConstraint(
            "rate > 0 AND rate <= 100", name="ck_commerce_commissions_rate"
        ),
        CheckConstraint("amount > 0", name="ck_commerce_commissions_amount"),
        CheckConstraint(
            "status IN ('accrued', 'approved', 'paid', 'cancelled')",
            name="ck_commerce_commissions_status",
        ),
        Index("ix_commerce_commissions_company_order", "company_id", "order_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("commerce_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    beneficiary_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    financial_entry_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("financial_entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="accrued")
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
