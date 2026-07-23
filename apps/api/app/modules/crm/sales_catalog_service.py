from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.authorization.service import record_authorization_audit
from app.modules.crm.sales_catalog_schemas import (
    PriceBookCreate,
    PriceBookEntryResponse,
    PriceBookEntryUpsert,
    PriceBookResponse,
    QuoteCreate,
    QuoteDecision,
    QuoteItemResponse,
    QuoteResponse,
)
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event

MONEY = Decimal("0.01")


class SalesCatalogError(RuntimeError):
    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def calculate_quote_line(
    quantity: Decimal, unit_price: Decimal, discount_percent: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    gross = (quantity * unit_price).quantize(MONEY, rounding=ROUND_HALF_UP)
    discount = (gross * discount_percent / Decimal("100")).quantize(
        MONEY, rounding=ROUND_HALF_UP
    )
    return gross, discount, (gross - discount).quantize(MONEY)


async def _price_book_response(
    database: AsyncSession, row: Any
) -> PriceBookResponse:
    entries = (
        await database.execute(
            text(
                """
                SELECT entry.id, entry.inventory_item_id, item.sku,
                       item.name AS item_name, item.unit, entry.unit_price,
                       entry.minimum_quantity, entry.active
                FROM crm_price_book_entries AS entry
                JOIN inventory_items AS item
                  ON item.id = entry.inventory_item_id
                 AND item.company_id = entry.company_id
                WHERE entry.company_id = :company_id
                  AND entry.price_book_id = :price_book_id
                ORDER BY item.name
                """
            ),
            {"company_id": row.company_id, "price_book_id": row.id},
        )
    ).all()
    return PriceBookResponse(
        id=row.id,
        name=row.name,
        currency=row.currency,
        status=row.status,
        version=row.version,
        is_default=row.is_default,
        valid_from=row.valid_from,
        valid_until=row.valid_until,
        published_at=row.published_at,
        entries=[PriceBookEntryResponse(**entry._mapping) for entry in entries],
        created_at=row.created_at,
    )


async def list_price_books(
    database: AsyncSession, *, company_id: UUID
) -> list[PriceBookResponse]:
    rows = (
        await database.execute(
            text(
                """
                SELECT *
                FROM crm_price_books
                WHERE company_id = :company_id
                ORDER BY is_default DESC, created_at DESC
                """
            ),
            {"company_id": company_id},
        )
    ).all()
    return [await _price_book_response(database, row) for row in rows]


async def create_price_book(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    payload: PriceBookCreate,
) -> PriceBookResponse:
    if payload.valid_from and payload.valid_until and payload.valid_until < payload.valid_from:
        raise SalesCatalogError("A validade final não pode ser anterior à inicial.")
    if payload.is_default:
        await database.execute(
            text(
                """
                UPDATE crm_price_books
                SET is_default = false, updated_at = now()
                WHERE company_id = :company_id AND is_default = true
                """
            ),
            {"company_id": company_id},
        )
    row = (
        await database.execute(
            text(
                """
                INSERT INTO crm_price_books (
                  company_id, name, currency, is_default, valid_from, valid_until,
                  created_by_user_id
                ) VALUES (
                  :company_id, :name, :currency, :is_default, :valid_from, :valid_until,
                  :actor_user_id
                )
                RETURNING *
                """
            ),
            {
                "company_id": company_id,
                "name": payload.name.strip(),
                "currency": payload.currency.upper(),
                "is_default": payload.is_default,
                "valid_from": payload.valid_from,
                "valid_until": payload.valid_until,
                "actor_user_id": actor_user_id,
            },
        )
    ).one()
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="crm.price_book.created",
        target_type="crm_price_book",
        target_id=row.id,
        details={"currency": row.currency, "version": row.version},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="crm.price_book.created",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="internal",
            payload={"price_book_id": str(row.id), "version": row.version},
        ),
    )
    await database.commit()
    return await _price_book_response(database, row)


async def upsert_price_book_entry(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    price_book_id: UUID,
    payload: PriceBookEntryUpsert,
) -> PriceBookResponse:
    price_book = (
        await database.execute(
            text(
                """
                SELECT * FROM crm_price_books
                WHERE company_id = :company_id AND id = :price_book_id
                FOR UPDATE
                """
            ),
            {"company_id": company_id, "price_book_id": price_book_id},
        )
    ).one_or_none()
    if price_book is None:
        raise SalesCatalogError("Tabela de preços não encontrada.", status_code=404)
    if price_book.status != "draft":
        raise SalesCatalogError(
            "Somente tabelas em rascunho podem receber preços.", status_code=409
        )
    item_exists = await database.scalar(
        text(
            """
            SELECT EXISTS (
              SELECT 1 FROM inventory_items
              WHERE company_id = :company_id AND id = :item_id
                AND active = true AND archived_at IS NULL
            )
            """
        ),
        {"company_id": company_id, "item_id": payload.inventory_item_id},
    )
    if not item_exists:
        raise SalesCatalogError("Produto inválido para esta empresa.")
    await database.execute(
        text(
            """
            INSERT INTO crm_price_book_entries (
              company_id, price_book_id, inventory_item_id, unit_price,
              minimum_quantity
            ) VALUES (
              :company_id, :price_book_id, :item_id, :unit_price, :minimum_quantity
            )
            ON CONFLICT (price_book_id, inventory_item_id) DO UPDATE
            SET unit_price = EXCLUDED.unit_price,
                minimum_quantity = EXCLUDED.minimum_quantity,
                active = true,
                updated_at = now()
            """
        ),
        {
            "company_id": company_id,
            "price_book_id": price_book_id,
            "item_id": payload.inventory_item_id,
            "unit_price": payload.unit_price,
            "minimum_quantity": payload.minimum_quantity,
        },
    )
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="crm.price_book.entry_upserted",
        target_type="crm_price_book",
        target_id=price_book_id,
        details={"inventory_item_id": str(payload.inventory_item_id)},
    )
    await database.commit()
    return await _price_book_response(database, price_book)


async def publish_price_book(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    price_book_id: UUID,
) -> PriceBookResponse:
    row = (
        await database.execute(
            text(
                """
                UPDATE crm_price_books AS book
                SET status = 'published', published_at = now(), updated_at = now()
                WHERE book.company_id = :company_id
                  AND book.id = :price_book_id
                  AND book.status = 'draft'
                  AND EXISTS (
                    SELECT 1 FROM crm_price_book_entries AS entry
                    WHERE entry.company_id = book.company_id
                      AND entry.price_book_id = book.id
                      AND entry.active = true
                  )
                RETURNING book.*
                """
            ),
            {"company_id": company_id, "price_book_id": price_book_id},
        )
    ).one_or_none()
    if row is None:
        raise SalesCatalogError(
            "A tabela precisa estar em rascunho e possuir ao menos um produto.",
            status_code=409,
        )
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="crm.price_book.published",
        target_type="crm_price_book",
        target_id=row.id,
        details={"version": row.version},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="crm.price_book.published",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="internal",
            payload={"price_book_id": str(row.id), "version": row.version},
        ),
    )
    await database.commit()
    return await _price_book_response(database, row)


async def _quote_response(database: AsyncSession, row: Any) -> QuoteResponse:
    items = (
        await database.execute(
            text(
                """
                SELECT id, inventory_item_id, sku_snapshot AS sku,
                       description_snapshot AS description, quantity, unit_price,
                       discount_percent, line_total
                FROM crm_quote_items
                WHERE company_id = :company_id AND quote_id = :quote_id
                ORDER BY created_at
                """
            ),
            {"company_id": row.company_id, "quote_id": row.id},
        )
    ).all()
    return QuoteResponse(
        id=row.id,
        opportunity_id=row.opportunity_id,
        account_id=row.account_id,
        price_book_id=row.price_book_id,
        quote_number=row.quote_number,
        title=row.title,
        status=row.status,
        version=row.version,
        valid_until=row.valid_until,
        subtotal=row.subtotal,
        discount_total=row.discount_total,
        total=row.total,
        notes=row.notes,
        items=[QuoteItemResponse(**item._mapping) for item in items],
        published_at=row.published_at,
        decided_at=row.decided_at,
        created_at=row.created_at,
    )


async def list_quotes(
    database: AsyncSession, *, company_id: UUID
) -> list[QuoteResponse]:
    rows = (
        await database.execute(
            text(
                """
                SELECT * FROM crm_quotes
                WHERE company_id = :company_id
                ORDER BY created_at DESC
                """
            ),
            {"company_id": company_id},
        )
    ).all()
    return [await _quote_response(database, row) for row in rows]


async def create_quote(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    payload: QuoteCreate,
) -> QuoteResponse:
    if payload.valid_until < date.today():
        raise SalesCatalogError("A proposta não pode nascer vencida.")
    opportunity = (
        await database.execute(
            text(
                """
                SELECT id, account_id
                FROM crm_opportunities
                WHERE company_id = :company_id AND id = :opportunity_id
                  AND deleted_at IS NULL AND status = 'open'
                """
            ),
            {"company_id": company_id, "opportunity_id": payload.opportunity_id},
        )
    ).one_or_none()
    if opportunity is None:
        raise SalesCatalogError("Oportunidade aberta não encontrada.")
    price_book = (
        await database.execute(
            text(
                """
                SELECT id, currency
                FROM crm_price_books
                WHERE company_id = :company_id AND id = :price_book_id
                  AND status = 'published'
                  AND (valid_from IS NULL OR valid_from <= CURRENT_DATE)
                  AND (valid_until IS NULL OR valid_until >= CURRENT_DATE)
                """
            ),
            {"company_id": company_id, "price_book_id": payload.price_book_id},
        )
    ).one_or_none()
    if price_book is None:
        raise SalesCatalogError("Tabela de preços publicada e vigente não encontrada.")

    unique_ids = {item.inventory_item_id for item in payload.items}
    if len(unique_ids) != len(payload.items):
        raise SalesCatalogError("Cada produto deve aparecer uma única vez na proposta.")
    price_rows = (
        await database.execute(
            text(
                """
                SELECT entry.inventory_item_id, entry.unit_price,
                       entry.minimum_quantity, item.sku, item.name
                FROM crm_price_book_entries AS entry
                JOIN inventory_items AS item
                  ON item.id = entry.inventory_item_id
                 AND item.company_id = entry.company_id
                WHERE entry.company_id = :company_id
                  AND entry.price_book_id = :price_book_id
                  AND entry.active = true
                  AND item.active = true
                  AND item.archived_at IS NULL
                  AND entry.inventory_item_id = ANY(:item_ids)
                """
            ),
            {
                "company_id": company_id,
                "price_book_id": payload.price_book_id,
                "item_ids": list(unique_ids),
            },
        )
    ).all()
    prices = {row.inventory_item_id: row for row in price_rows}
    if len(prices) != len(payload.items):
        raise SalesCatalogError("Um ou mais produtos não pertencem à tabela selecionada.")

    quote_id = uuid4()
    quote_number = f"COT-{date.today():%Y%m%d}-{quote_id.hex[:8].upper()}"
    subtotal = Decimal("0")
    discount_total = Decimal("0")
    prepared: list[dict[str, Any]] = []
    for requested in payload.items:
        priced = prices[requested.inventory_item_id]
        if requested.quantity < priced.minimum_quantity:
            raise SalesCatalogError(
                f"A quantidade de {priced.sku} é menor que o mínimo comercial."
            )
        gross, discount, total = calculate_quote_line(
            requested.quantity, priced.unit_price, requested.discount_percent
        )
        subtotal += gross
        discount_total += discount
        prepared.append(
            {
                "id": uuid4(),
                "inventory_item_id": requested.inventory_item_id,
                "sku": priced.sku,
                "description": priced.name,
                "quantity": requested.quantity,
                "unit_price": priced.unit_price,
                "discount_percent": requested.discount_percent,
                "line_total": total,
            }
        )
    total = (subtotal - discount_total).quantize(MONEY)
    row = (
        await database.execute(
            text(
                """
                INSERT INTO crm_quotes (
                  id, company_id, opportunity_id, account_id, price_book_id,
                  quote_number, title, valid_until, subtotal, discount_total,
                  total, notes, created_by_user_id
                ) VALUES (
                  :id, :company_id, :opportunity_id, :account_id, :price_book_id,
                  :quote_number, :title, :valid_until, :subtotal, :discount_total,
                  :total, :notes, :actor_user_id
                )
                RETURNING *
                """
            ),
            {
                "id": quote_id,
                "company_id": company_id,
                "opportunity_id": opportunity.id,
                "account_id": opportunity.account_id,
                "price_book_id": payload.price_book_id,
                "quote_number": quote_number,
                "title": payload.title.strip(),
                "valid_until": payload.valid_until,
                "subtotal": subtotal,
                "discount_total": discount_total,
                "total": total,
                "notes": payload.notes,
                "actor_user_id": actor_user_id,
            },
        )
    ).one()
    for item in prepared:
        await database.execute(
            text(
                """
                INSERT INTO crm_quote_items (
                  id, company_id, quote_id, inventory_item_id, sku_snapshot,
                  description_snapshot, quantity, unit_price, discount_percent,
                  line_total
                ) VALUES (
                  :id, :company_id, :quote_id, :inventory_item_id, :sku,
                  :description, :quantity, :unit_price, :discount_percent,
                  :line_total
                )
                """
            ),
            {"company_id": company_id, "quote_id": quote_id, **item},
        )
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="crm.quote.created",
        target_type="crm_quote",
        target_id=quote_id,
        details={
            "opportunity_id": str(opportunity.id),
            "item_count": len(prepared),
            "currency": price_book.currency,
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="crm.quote.created",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={
                "quote_id": str(quote_id),
                "opportunity_id": str(opportunity.id),
                "item_count": len(prepared),
            },
        ),
    )
    await database.commit()
    return await _quote_response(database, row)


async def publish_quote(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    quote_id: UUID,
) -> QuoteResponse:
    row = (
        await database.execute(
            text(
                """
                UPDATE crm_quotes
                SET status = 'published', published_at = now(), updated_at = now()
                WHERE company_id = :company_id AND id = :quote_id
                  AND status = 'draft' AND valid_until >= CURRENT_DATE
                RETURNING *
                """
            ),
            {"company_id": company_id, "quote_id": quote_id},
        )
    ).one_or_none()
    if row is None:
        raise SalesCatalogError(
            "Somente propostas válidas em rascunho podem ser publicadas.",
            status_code=409,
        )
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="crm.quote.published",
        target_type="crm_quote",
        target_id=row.id,
        details={"opportunity_id": str(row.opportunity_id), "version": row.version},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="crm.quote.published",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={
                "quote_id": str(row.id),
                "opportunity_id": str(row.opportunity_id),
                "version": row.version,
            },
        ),
    )
    await database.commit()
    return await _quote_response(database, row)


async def decide_quote(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    quote_id: UUID,
    payload: QuoteDecision,
) -> QuoteResponse:
    row = (
        await database.execute(
            text(
                """
                UPDATE crm_quotes
                SET status = :decision, decided_at = now(), updated_at = now()
                WHERE company_id = :company_id AND id = :quote_id
                  AND status = 'published' AND valid_until >= CURRENT_DATE
                RETURNING *
                """
            ),
            {
                "company_id": company_id,
                "quote_id": quote_id,
                "decision": payload.decision,
            },
        )
    ).one_or_none()
    if row is None:
        raise SalesCatalogError(
            "Somente propostas publicadas e válidas podem ser decididas.",
            status_code=409,
        )
    await database.execute(
        text(
            """
            INSERT INTO crm_opportunity_activities (
              company_id, opportunity_id, actor_user_id, activity_type,
              subject, body
            ) VALUES (
              :company_id, :opportunity_id, :actor_user_id, 'status_change',
              :subject, :body
            )
            """
        ),
        {
            "company_id": company_id,
            "opportunity_id": row.opportunity_id,
            "actor_user_id": actor_user_id,
            "subject": f"Proposta {payload.decision}",
            "body": payload.note,
        },
    )
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action=f"crm.quote.{payload.decision}",
        target_type="crm_quote",
        target_id=row.id,
        details={"opportunity_id": str(row.opportunity_id)},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=f"crm.quote.{payload.decision}",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={
                "quote_id": str(row.id),
                "opportunity_id": str(row.opportunity_id),
            },
        ),
    )
    await database.commit()
    return await _quote_response(database, row)
