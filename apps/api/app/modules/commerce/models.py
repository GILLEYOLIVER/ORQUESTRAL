from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CommerceProductVariant(Base):
    __tablename__ = "commerce_product_variants"
    __table_args__ = (
        UniqueConstraint("company_id", "sku", name="uq_commerce_variants_company_sku"),
        Index("ix_commerce_variants_company_item", "company_id", "inventory_item_id"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    inventory_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True
    )
    sku: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class CommercePromotion(Base):
    __tablename__ = "commerce_promotions"
    __table_args__ = (
        CheckConstraint(
            "discount_type IN ('percent','fixed')",
            name="ck_commerce_promotions_discount_type",
        ),
        CheckConstraint(
            "status IN ('draft','active','paused','expired')",
            name="ck_commerce_promotions_status",
        ),
        CheckConstraint(
            "applies_to IN ('all','item','variant')",
            name="ck_commerce_promotions_applies_to",
        ),
        CheckConstraint("discount_value >= 0", name="ck_commerce_promotions_value"),
        CheckConstraint(
            "discount_type <> 'percent' OR discount_value <= 100",
            name="ck_commerce_promotions_percent",
        ),
        CheckConstraint("minimum_quantity > 0", name="ck_commerce_promotions_minimum"),
        CheckConstraint(
            "max_redemptions IS NULL OR max_redemptions > 0",
            name="ck_commerce_promotions_max_redemptions",
        ),
        CheckConstraint("redeemed_count >= 0", name="ck_commerce_promotions_redeemed"),
        CheckConstraint(
            "(applies_to = 'all' AND inventory_item_id IS NULL AND variant_id IS NULL) OR "
            "(applies_to = 'item' AND inventory_item_id IS NOT NULL AND variant_id IS NULL) OR "
            "(applies_to = 'variant' AND variant_id IS NOT NULL)",
            name="ck_commerce_promotions_target",
        ),
        UniqueConstraint("company_id", "code", name="uq_commerce_promotions_company_code"),
        Index("ix_commerce_promotions_company_status", "company_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    inventory_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("commerce_product_variants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(180), index=True)
    code: Mapped[str | None] = mapped_column(String(80), index=True)
    discount_type: Mapped[str] = mapped_column(String(16))
    discount_value: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    applies_to: Mapped[str] = mapped_column(String(16))
    minimum_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("1"), server_default="1"
    )
    max_redemptions: Mapped[int | None] = mapped_column(Integer)
    redeemed_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(
        String(16), default="draft", server_default="draft", index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )
