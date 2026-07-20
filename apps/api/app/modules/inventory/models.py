from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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


class InventoryCategory(Base):
    __tablename__ = "inventory_categories"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_inventory_categories_company_name"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class InventoryLocation(Base):
    __tablename__ = "inventory_locations"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_inventory_locations_company_code"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(140), index=True)
    description: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        CheckConstraint(
            "unit IN ('unit', 'kg', 'g', 'l', 'ml', 'm', 'box')",
            name="ck_inventory_items_unit",
        ),
        CheckConstraint("minimum_stock >= 0", name="ck_inventory_items_minimum_stock"),
        UniqueConstraint("company_id", "sku", name="uq_inventory_items_company_sku"),
        Index("ix_inventory_items_company_active", "company_id", "active"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("inventory_categories.id", ondelete="SET NULL"), index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    sku: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(20), default="unit", server_default="unit")
    minimum_stock: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("0"), server_default="0"
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class InventoryBalance(Base):
    __tablename__ = "inventory_balances"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_inventory_balances_quantity"),
        UniqueConstraint("item_id", "location_id", name="uq_inventory_balances_item_location"),
        Index("ix_inventory_balances_company_item", "company_id", "item_id"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True
    )
    location_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_locations.id", ondelete="CASCADE"), index=True
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("0"), server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('in', 'out', 'adjustment')",
            name="ck_inventory_movements_type",
        ),
        CheckConstraint("quantity > 0", name="ck_inventory_movements_quantity"),
        CheckConstraint(
            "previous_quantity >= 0 AND resulting_quantity >= 0",
            name="ck_inventory_movements_balances",
        ),
        Index("ix_inventory_movements_company_occurred", "company_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_locations.id", ondelete="RESTRICT"), index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    movement_type: Mapped[str] = mapped_column(String(20), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    previous_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    resulting_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    reason: Mapped[str] = mapped_column(String(300))
    reference: Mapped[str | None] = mapped_column(String(120), index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
