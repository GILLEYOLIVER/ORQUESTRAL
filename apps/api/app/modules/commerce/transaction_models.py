from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CommerceOrder(Base):
    __tablename__ = "commerce_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','reserved','confirmed','fulfilled','cancelled')",
            name="ck_commerce_orders_status",
        ),
        CheckConstraint(
            "subtotal >= 0 AND discount_total >= 0 AND total >= 0",
            name="ck_commerce_orders_totals",
        ),
        UniqueConstraint("company_id", "order_number", name="uq_commerce_orders_number"),
        UniqueConstraint("quote_id", name="uq_commerce_orders_quote"),
        UniqueConstraint(
            "company_id", "idempotency_key", name="uq_commerce_orders_idempotency"
        ),
        Index("ix_commerce_orders_company_status", "company_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    quote_id: Mapped[UUID] = mapped_column(
        ForeignKey("crm_quotes.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("crm_accounts.id", ondelete="SET NULL"), index=True
    )
    financial_entry_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("financial_entries.id", ondelete="SET NULL"), unique=True, index=True
    )
    order_number: Mapped[str] = mapped_column(String(60), index=True)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", index=True
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    discount_total: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class CommerceOrderItem(Base):
    __tablename__ = "commerce_order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_commerce_order_items_quantity"),
        CheckConstraint(
            "unit_price >= 0 AND discount_total >= 0 AND line_total >= 0",
            name="ck_commerce_order_items_totals",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("commerce_orders.id", ondelete="CASCADE"), index=True
    )
    inventory_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), index=True
    )
    variant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("commerce_product_variants.id", ondelete="SET NULL"), index=True
    )
    sku_snapshot: Mapped[str] = mapped_column(String(100))
    description_snapshot: Mapped[str] = mapped_column(String(300))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    discount_total: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


from app.modules.commerce import settlement_models as _settlement_models  # noqa: E402,F401


class CommerceInventoryReservation(Base):
    __tablename__ = "commerce_inventory_reservations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('reserved','consumed','released')",
            name="ck_commerce_reservations_status",
        ),
        CheckConstraint("quantity > 0", name="ck_commerce_reservations_quantity"),
        UniqueConstraint("order_item_id", name="uq_commerce_reservations_order_item"),
        Index(
            "ix_commerce_reservations_availability",
            "company_id",
            "inventory_item_id",
            "location_id",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("commerce_orders.id", ondelete="CASCADE"), index=True
    )
    order_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("commerce_order_items.id", ondelete="CASCADE"), index=True
    )
    inventory_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_locations.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    status: Mapped[str] = mapped_column(
        String(16), default="reserved", server_default="reserved", index=True
    )
    reserved_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CommerceContract(Base):
    __tablename__ = "commerce_contracts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','active','suspended','completed','cancelled')",
            name="ck_commerce_contracts_status",
        ),
        CheckConstraint("total_value >= 0", name="ck_commerce_contracts_total"),
        CheckConstraint(
            "ends_on IS NULL OR ends_on >= starts_on", name="ck_commerce_contracts_period"
        ),
        UniqueConstraint("company_id", "contract_number", name="uq_commerce_contracts_number"),
        UniqueConstraint("order_id", name="uq_commerce_contracts_order"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("commerce_orders.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("crm_accounts.id", ondelete="SET NULL"), index=True
    )
    contract_number: Mapped[str] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", index=True
    )
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    total_value: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    terms: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


class CommerceCustomerSubscription(Base):
    __tablename__ = "commerce_customer_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','paused','past_due','cancelled','completed')",
            name="ck_commerce_customer_subscriptions_status",
        ),
        CheckConstraint(
            "billing_interval IN ('monthly','yearly')",
            name="ck_commerce_customer_subscriptions_interval",
        ),
        CheckConstraint("amount >= 0", name="ck_commerce_customer_subscriptions_amount"),
        CheckConstraint(
            "current_period_end > current_period_start",
            name="ck_commerce_customer_subscriptions_period",
        ),
        UniqueConstraint("contract_id", name="uq_commerce_customer_subscriptions_contract"),
        Index(
            "ix_commerce_customer_subscriptions_company_status", "company_id", "status"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("commerce_contracts.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("crm_accounts.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", index=True
    )
    billing_interval: Mapped[str] = mapped_column(String(16))
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    current_period_start: Mapped[date] = mapped_column(Date)
    current_period_end: Mapped[date] = mapped_column(Date)
    next_billing_on: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
