from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select, text

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.commerce.models import CommerceProductVariant, CommercePromotion
from app.modules.commerce.schemas import (
    PriceResolutionRequest,
    PriceResolutionResponse,
    ProductVariantCreate,
    ProductVariantResponse,
    PromotionCreate,
    PromotionResponse,
)
from app.modules.commerce.service import MONEY, calculate_discount
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.inventory.models import InventoryItem
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(
    prefix="/commerce",
    tags=["commerce"],
    dependencies=[Depends(require_active_module("commerce"))],
)
CanView = Annotated[Principal, Depends(require_permission("commerce.view"))]
CanManageCatalog = Annotated[
    Principal, Depends(require_permission("commerce.catalog.manage"))
]
CanManagePromotions = Annotated[
    Principal, Depends(require_permission("commerce.promotions.manage"))
]
CanResolvePrice = Annotated[
    Principal, Depends(require_permission("commerce.pricing.resolve"))
]


@router.get("/variants", response_model=list[ProductVariantResponse])
async def list_variants(
    principal: CanView, database: DatabaseSession
) -> list[ProductVariantResponse]:
    context = get_request_context(principal)
    rows = (
        await database.scalars(
            select(CommerceProductVariant)
            .where(CommerceProductVariant.company_id == context.company_id)
            .order_by(CommerceProductVariant.name)
        )
    ).all()
    return [
        ProductVariantResponse.model_validate(row, from_attributes=True) for row in rows
    ]


@router.post(
    "/variants",
    response_model=ProductVariantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_variant(
    payload: ProductVariantCreate,
    principal: CanManageCatalog,
    database: DatabaseSession,
) -> ProductVariantResponse:
    context = get_request_context(principal)
    item = await database.scalar(
        select(InventoryItem.id).where(
            InventoryItem.id == payload.inventory_item_id,
            InventoryItem.company_id == context.company_id,
            InventoryItem.active.is_(True),
            InventoryItem.archived_at.is_(None),
        )
    )
    if item is None:
        raise HTTPException(status_code=422, detail="Produto ativo não encontrado.")
    row = CommerceProductVariant(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        inventory_item_id=payload.inventory_item_id,
        sku=payload.sku.strip().upper(),
        name=payload.name.strip(),
        attributes=payload.attributes,
    )
    database.add(row)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="commerce.variant.created",
        target_type="commerce_product_variant",
        target_id=row.id,
        details={"inventory_item_id": str(payload.inventory_item_id)},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="commerce.variant.created",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="internal",
            payload={"variant_id": str(row.id), "inventory_item_id": str(item)},
        ),
    )
    await database.commit()
    await database.refresh(row)
    return ProductVariantResponse.model_validate(row, from_attributes=True)


@router.get("/promotions", response_model=list[PromotionResponse])
async def list_promotions(
    principal: CanView, database: DatabaseSession
) -> list[PromotionResponse]:
    context = get_request_context(principal)
    rows = (
        await database.scalars(
            select(CommercePromotion)
            .where(CommercePromotion.company_id == context.company_id)
            .order_by(CommercePromotion.created_at.desc())
        )
    ).all()
    return [PromotionResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post(
    "/promotions",
    response_model=PromotionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_promotion(
    payload: PromotionCreate,
    principal: CanManagePromotions,
    database: DatabaseSession,
) -> PromotionResponse:
    context = get_request_context(principal)
    if payload.inventory_item_id is not None:
        item = await database.scalar(
            select(InventoryItem.id).where(
                InventoryItem.id == payload.inventory_item_id,
                InventoryItem.company_id == context.company_id,
                InventoryItem.active.is_(True),
            )
        )
        if item is None:
            raise HTTPException(status_code=422, detail="Produto inválido para a promoção.")
    if payload.variant_id is not None:
        variant = await database.scalar(
            select(CommerceProductVariant).where(
                CommerceProductVariant.id == payload.variant_id,
                CommerceProductVariant.company_id == context.company_id,
                CommerceProductVariant.active.is_(True),
            )
        )
        if variant is None:
            raise HTTPException(status_code=422, detail="Variante inválida para a promoção.")
        if (
            payload.inventory_item_id is not None
            and variant.inventory_item_id != payload.inventory_item_id
        ):
            raise HTTPException(status_code=422, detail="Variante não pertence ao produto.")
    values = payload.model_dump()
    values["code"] = payload.code.strip().upper() if payload.code else None
    row = CommercePromotion(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **values,
    )
    database.add(row)
    await database.commit()
    await database.refresh(row)
    return PromotionResponse.model_validate(row, from_attributes=True)


@router.post("/promotions/{promotion_id}/activate", response_model=PromotionResponse)
async def activate_promotion(
    promotion_id: UUID,
    principal: CanManagePromotions,
    database: DatabaseSession,
) -> PromotionResponse:
    context = get_request_context(principal)
    row = await database.scalar(
        select(CommercePromotion).where(
            CommercePromotion.id == promotion_id,
            CommercePromotion.company_id == context.company_id,
            CommercePromotion.status == "draft",
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Promoção em rascunho não encontrada.")
    if row.ends_at is not None and row.ends_at <= utc_now():
        raise HTTPException(status_code=409, detail="A promoção já está vencida.")
    row.status = "active"
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="commerce.promotion.activated",
        target_type="commerce_promotion",
        target_id=row.id,
        details={"code": row.code, "applies_to": row.applies_to},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="commerce.promotion.activated",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="internal",
            payload={"promotion_id": str(row.id)},
        ),
    )
    await database.commit()
    return PromotionResponse.model_validate(row, from_attributes=True)


@router.post("/pricing/resolve", response_model=PriceResolutionResponse)
async def resolve_price(
    payload: PriceResolutionRequest,
    principal: CanResolvePrice,
    database: DatabaseSession,
) -> PriceResolutionResponse:
    context = get_request_context(principal)
    base = (
        await database.execute(
            text(
                """
                SELECT book.currency, entry.unit_price, entry.minimum_quantity
                FROM crm_price_books AS book
                JOIN crm_price_book_entries AS entry
                  ON entry.price_book_id = book.id
                 AND entry.company_id = book.company_id
                JOIN inventory_items AS item
                  ON item.id = entry.inventory_item_id
                 AND item.company_id = entry.company_id
                WHERE book.company_id = :company_id
                  AND book.id = :price_book_id
                  AND book.status = 'published'
                  AND (book.valid_from IS NULL OR book.valid_from <= CURRENT_DATE)
                  AND (book.valid_until IS NULL OR book.valid_until >= CURRENT_DATE)
                  AND entry.inventory_item_id = :item_id
                  AND entry.active = true
                  AND item.active = true
                  AND item.archived_at IS NULL
                """
            ),
            {
                "company_id": context.company_id,
                "price_book_id": payload.price_book_id,
                "item_id": payload.inventory_item_id,
            },
        )
    ).one_or_none()
    if base is None or payload.quantity < base.minimum_quantity:
        raise HTTPException(
            status_code=422,
            detail="Preço publicado não encontrado ou quantidade abaixo do mínimo.",
        )
    if payload.variant_id is not None:
        valid_variant = await database.scalar(
            select(CommerceProductVariant.id).where(
                CommerceProductVariant.id == payload.variant_id,
                CommerceProductVariant.company_id == context.company_id,
                CommerceProductVariant.inventory_item_id == payload.inventory_item_id,
                CommerceProductVariant.active.is_(True),
            )
        )
        if valid_variant is None:
            raise HTTPException(status_code=422, detail="Variante inválida para o produto.")
    now = utc_now()
    conditions = [
        CommercePromotion.company_id == context.company_id,
        CommercePromotion.status == "active",
        CommercePromotion.starts_at <= now,
        or_(CommercePromotion.ends_at.is_(None), CommercePromotion.ends_at > now),
        CommercePromotion.minimum_quantity <= payload.quantity,
        or_(
            CommercePromotion.max_redemptions.is_(None),
            CommercePromotion.redeemed_count < CommercePromotion.max_redemptions,
        ),
        or_(
            CommercePromotion.applies_to == "all",
            (
                (CommercePromotion.applies_to == "item")
                & (CommercePromotion.inventory_item_id == payload.inventory_item_id)
            ),
            (
                (CommercePromotion.applies_to == "variant")
                & (CommercePromotion.variant_id == payload.variant_id)
            ),
        ),
    ]
    if payload.promotion_code:
        conditions.append(
            CommercePromotion.code == payload.promotion_code.strip().upper()
        )
    promotions = (await database.scalars(select(CommercePromotion).where(*conditions))).all()
    base_price = Decimal(base.unit_price)
    candidates = [
        (calculate_discount(base_price, row.discount_type, row.discount_value), row)
        for row in promotions
    ]
    discount, promotion = max(candidates, key=lambda item: item[0], default=(Decimal("0"), None))
    final_unit = (base_price - discount).quantize(MONEY, rounding=ROUND_HALF_UP)
    total = (final_unit * payload.quantity).quantize(MONEY, rounding=ROUND_HALF_UP)
    return PriceResolutionResponse(
        currency=base.currency,
        quantity=payload.quantity,
        base_unit_price=base_price,
        discount_per_unit=discount,
        final_unit_price=final_unit,
        total=total,
        promotion_id=promotion.id if promotion else None,
        promotion_name=promotion.name if promotion else None,
        evidence={
            "price_book_id": str(payload.price_book_id),
            "inventory_item_id": str(payload.inventory_item_id),
            "variant_id": str(payload.variant_id) if payload.variant_id else None,
            "eligible_promotions": len(promotions),
            "rule": "highest_discount_wins",
        },
    )
