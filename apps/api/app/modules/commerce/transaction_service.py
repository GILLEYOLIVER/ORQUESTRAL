from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utc_now
from app.modules.authorization.service import record_authorization_audit
from app.modules.commerce.transaction_schemas import (
    ContractResponse,
    OrderConfirm,
    OrderFromQuoteCreate,
    OrderItemResponse,
    OrderResponse,
)
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event


class CommerceTransactionError(RuntimeError):
    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def next_period(start: date, interval: str) -> date:
    if interval == "yearly":
        try:
            return start.replace(year=start.year + 1)
        except ValueError:
            return start.replace(year=start.year + 1, day=28)
    month_index = start.month
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(start.day, monthrange(year, month)[1]))


async def _order_response(database: AsyncSession, row: Any) -> OrderResponse:
    items = (
        await database.execute(
            text(
                """
                SELECT id, inventory_item_id, sku_snapshot AS sku,
                       description_snapshot AS description, quantity, unit_price,
                       discount_total, line_total
                FROM commerce_order_items
                WHERE company_id = :company_id AND order_id = :order_id
                ORDER BY created_at, id
                """
            ),
            {"company_id": row.company_id, "order_id": row.id},
        )
    ).all()
    return OrderResponse(
        id=row.id,
        quote_id=row.quote_id,
        account_id=row.account_id,
        financial_entry_id=row.financial_entry_id,
        order_number=row.order_number,
        currency=row.currency,
        status=row.status,
        subtotal=row.subtotal,
        discount_total=row.discount_total,
        total=row.total,
        items=[OrderItemResponse(**item._mapping) for item in items],
        confirmed_at=row.confirmed_at,
        created_at=row.created_at,
    )


async def list_orders(database: AsyncSession, *, company_id: UUID) -> list[OrderResponse]:
    rows = (
        await database.execute(
            text(
                """
                SELECT * FROM commerce_orders
                WHERE company_id = :company_id
                ORDER BY created_at DESC
                """
            ),
            {"company_id": company_id},
        )
    ).all()
    return [await _order_response(database, row) for row in rows]


async def create_order_from_quote(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    payload: OrderFromQuoteCreate,
) -> OrderResponse:
    await database.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
        {"scope": f"commerce-order:{company_id}:{payload.quote_id}"},
    )
    existing = (
        await database.execute(
            text(
                """
                SELECT * FROM commerce_orders
                WHERE company_id = :company_id AND idempotency_key = :key
                """
            ),
            {"company_id": company_id, "key": payload.idempotency_key},
        )
    ).one_or_none()
    if existing is not None:
        return await _order_response(database, existing)
    quote = (
        await database.execute(
            text(
                """
                SELECT quote.*, book.currency
                FROM crm_quotes AS quote
                JOIN crm_price_books AS book
                  ON book.id = quote.price_book_id
                 AND book.company_id = quote.company_id
                WHERE quote.company_id = :company_id
                  AND quote.id = :quote_id
                  AND quote.status = 'accepted'
                FOR UPDATE OF quote
                """
            ),
            {"company_id": company_id, "quote_id": payload.quote_id},
        )
    ).one_or_none()
    if quote is None:
        raise CommerceTransactionError("Apenas propostas aceitas podem gerar pedidos.")
    previous = await database.scalar(
        text(
            """
            SELECT EXISTS (
              SELECT 1 FROM commerce_orders
              WHERE company_id = :company_id AND quote_id = :quote_id
                AND status <> 'cancelled'
            )
            """
        ),
        {"company_id": company_id, "quote_id": payload.quote_id},
    )
    if previous:
        raise CommerceTransactionError(
            "Esta proposta já possui um pedido ativo.", status_code=409
        )
    quote_items = (
        await database.execute(
            text(
                """
                SELECT * FROM crm_quote_items
                WHERE company_id = :company_id AND quote_id = :quote_id
                ORDER BY created_at, id
                """
            ),
            {"company_id": company_id, "quote_id": payload.quote_id},
        )
    ).all()
    if not quote_items:
        raise CommerceTransactionError("A proposta não possui itens.")
    order_id = uuid4()
    order_number = f"PED-{utc_now():%Y%m%d}-{order_id.hex[:8].upper()}"
    row = (
        await database.execute(
            text(
                """
                INSERT INTO commerce_orders (
                  id, company_id, quote_id, account_id, order_number, currency,
                  subtotal, discount_total, total, idempotency_key, created_by_user_id
                ) VALUES (
                  :id, :company_id, :quote_id, :account_id, :order_number, :currency,
                  :subtotal, :discount_total, :total, :key, :actor_user_id
                ) RETURNING *
                """
            ),
            {
                "id": order_id,
                "company_id": company_id,
                "quote_id": quote.id,
                "account_id": quote.account_id,
                "order_number": order_number,
                "currency": quote.currency,
                "subtotal": quote.subtotal,
                "discount_total": quote.discount_total,
                "total": quote.total,
                "key": payload.idempotency_key,
                "actor_user_id": actor_user_id,
            },
        )
    ).one()
    for item in quote_items:
        gross = Decimal(item.quantity) * Decimal(item.unit_price)
        discount = gross - Decimal(item.line_total)
        await database.execute(
            text(
                """
                INSERT INTO commerce_order_items (
                  id, company_id, order_id, inventory_item_id, sku_snapshot,
                  description_snapshot, quantity, unit_price, discount_total, line_total
                ) VALUES (
                  gen_random_uuid(), :company_id, :order_id, :item_id, :sku,
                  :description, :quantity, :unit_price, :discount_total, :line_total
                )
                """
            ),
            {
                "company_id": company_id,
                "order_id": order_id,
                "item_id": item.inventory_item_id,
                "sku": item.sku_snapshot,
                "description": item.description_snapshot,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "discount_total": discount,
                "line_total": item.line_total,
            },
        )
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="commerce.order.created",
        target_type="commerce_order",
        target_id=order_id,
        details={"quote_id": str(quote.id), "order_number": order_number},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="commerce.order.created",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={"order_id": str(order_id), "quote_id": str(quote.id)},
        ),
    )
    await database.commit()
    return await _order_response(database, row)


async def reserve_order(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    order_id: UUID,
    location_id: UUID,
) -> OrderResponse:
    order = (
        await database.execute(
            text(
                """
                SELECT * FROM commerce_orders
                WHERE company_id = :company_id AND id = :order_id
                FOR UPDATE
                """
            ),
            {"company_id": company_id, "order_id": order_id},
        )
    ).one_or_none()
    if order is None:
        raise CommerceTransactionError("Pedido não encontrado.", status_code=404)
    if order.status == "reserved":
        return await _order_response(database, order)
    if order.status != "draft":
        raise CommerceTransactionError(
            "Somente pedidos em rascunho podem reservar estoque.", status_code=409
        )
    location = await database.scalar(
        text(
            """
            SELECT id FROM inventory_locations
            WHERE company_id = :company_id AND id = :location_id AND active = true
            """
        ),
        {"company_id": company_id, "location_id": location_id},
    )
    if location is None:
        raise CommerceTransactionError("Local de estoque ativo não encontrado.")
    items = (
        await database.execute(
            text(
                """
                SELECT * FROM commerce_order_items
                WHERE company_id = :company_id AND order_id = :order_id
                ORDER BY inventory_item_id
                """
            ),
            {"company_id": company_id, "order_id": order_id},
        )
    ).all()
    for item in items:
        balance = (
            await database.execute(
                text(
                    """
                    SELECT * FROM inventory_balances
                    WHERE company_id = :company_id AND item_id = :item_id
                      AND location_id = :location_id
                    FOR UPDATE
                    """
                ),
                {
                    "company_id": company_id,
                    "item_id": item.inventory_item_id,
                    "location_id": location_id,
                },
            )
        ).one_or_none()
        reserved = Decimal(
            await database.scalar(
                text(
                    """
                    SELECT COALESCE(SUM(quantity), 0)
                    FROM commerce_inventory_reservations
                    WHERE company_id = :company_id AND inventory_item_id = :item_id
                      AND location_id = :location_id AND status = 'reserved'
                    """
                ),
                {
                    "company_id": company_id,
                    "item_id": item.inventory_item_id,
                    "location_id": location_id,
                },
            )
            or 0
        )
        if balance is None or Decimal(balance.quantity) - reserved < Decimal(item.quantity):
            raise CommerceTransactionError(
                f"Estoque disponível insuficiente para {item.sku_snapshot}.",
                status_code=409,
            )
        await database.execute(
            text(
                """
                INSERT INTO commerce_inventory_reservations (
                  id, company_id, order_id, order_item_id, inventory_item_id,
                  location_id, quantity, reserved_by_user_id
                ) VALUES (
                  gen_random_uuid(), :company_id, :order_id, :order_item_id, :item_id,
                  :location_id, :quantity, :actor_user_id
                )
                """
            ),
            {
                "company_id": company_id,
                "order_id": order_id,
                "order_item_id": item.id,
                "item_id": item.inventory_item_id,
                "location_id": location_id,
                "quantity": item.quantity,
                "actor_user_id": actor_user_id,
            },
        )
    updated = (
        await database.execute(
            text(
                """
                UPDATE commerce_orders SET status='reserved', updated_at=now()
                WHERE company_id=:company_id AND id=:order_id
                RETURNING *
                """
            ),
            {"company_id": company_id, "order_id": order_id},
        )
    ).one()
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="commerce.order.reserved",
        target_type="commerce_order",
        target_id=order_id,
        details={"location_id": str(location_id)},
    )
    await database.commit()
    return await _order_response(database, updated)


async def confirm_order(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    order_id: UUID,
    payload: OrderConfirm,
) -> OrderResponse:
    order = (
        await database.execute(
            text(
                """
                SELECT * FROM commerce_orders
                WHERE company_id = :company_id AND id = :order_id
                FOR UPDATE
                """
            ),
            {"company_id": company_id, "order_id": order_id},
        )
    ).one_or_none()
    if order is None:
        raise CommerceTransactionError("Pedido não encontrado.", status_code=404)
    if order.status == "confirmed":
        return await _order_response(database, order)
    if order.status != "reserved":
        raise CommerceTransactionError(
            "Reserve o estoque antes de confirmar o pedido.", status_code=409
        )
    if payload.account_id is not None:
        valid_account = await database.scalar(
            text(
                """
                SELECT EXISTS (
                  SELECT 1 FROM financial_accounts
                  WHERE company_id=:company_id AND id=:id AND active=true
                )
                """
            ),
            {"company_id": company_id, "id": payload.account_id},
        )
        if not valid_account:
            raise CommerceTransactionError("Conta financeira inválida.")
    if payload.category_id is not None:
        valid_category = await database.scalar(
            text(
                """
                SELECT EXISTS (
                  SELECT 1 FROM financial_categories
                  WHERE company_id=:company_id AND id=:id
                    AND active=true AND entry_type='income'
                )
                """
            ),
            {"company_id": company_id, "id": payload.category_id},
        )
        if not valid_category:
            raise CommerceTransactionError("Categoria de receita inválida.")
    reservations = (
        await database.execute(
            text(
                """
                SELECT reservation.*, item.sku_snapshot
                FROM commerce_inventory_reservations AS reservation
                JOIN commerce_order_items AS item
                  ON item.id=reservation.order_item_id
                 AND item.company_id=reservation.company_id
                WHERE reservation.company_id=:company_id
                  AND reservation.order_id=:order_id
                  AND reservation.status='reserved'
                ORDER BY reservation.inventory_item_id
                """
            ),
            {"company_id": company_id, "order_id": order_id},
        )
    ).all()
    if not reservations:
        raise CommerceTransactionError("O pedido não possui reservas ativas.", status_code=409)
    for reservation in reservations:
        balance = (
            await database.execute(
                text(
                    """
                    SELECT * FROM inventory_balances
                    WHERE company_id=:company_id AND item_id=:item_id
                      AND location_id=:location_id
                    FOR UPDATE
                    """
                ),
                {
                    "company_id": company_id,
                    "item_id": reservation.inventory_item_id,
                    "location_id": reservation.location_id,
                },
            )
        ).one_or_none()
        if balance is None or Decimal(balance.quantity) < Decimal(reservation.quantity):
            raise CommerceTransactionError(
                f"Saldo alterado e insuficiente para {reservation.sku_snapshot}.",
                status_code=409,
            )
        previous = Decimal(balance.quantity)
        resulting = previous - Decimal(reservation.quantity)
        await database.execute(
            text(
                """
                UPDATE inventory_balances SET quantity=:resulting, updated_at=now()
                WHERE company_id=:company_id AND id=:balance_id
                """
            ),
            {
                "resulting": resulting,
                "company_id": company_id,
                "balance_id": balance.id,
            },
        )
        await database.execute(
            text(
                """
                INSERT INTO inventory_movements (
                  id,company_id,item_id,location_id,created_by_user_id,
                  movement_type,quantity,previous_quantity,resulting_quantity,
                  reason,reference
                ) VALUES (
                  gen_random_uuid(),:company_id,:item_id,:location_id,:actor_user_id,
                  'out',:quantity,:previous,:resulting,
                  'Confirmação de pedido',:reference
                )
                """
            ),
            {
                "company_id": company_id,
                "item_id": reservation.inventory_item_id,
                "location_id": reservation.location_id,
                "actor_user_id": actor_user_id,
                "quantity": reservation.quantity,
                "previous": previous,
                "resulting": resulting,
                "reference": order.order_number,
            },
        )
    await database.execute(
        text(
            """
            UPDATE commerce_inventory_reservations
            SET status='consumed',consumed_at=now()
            WHERE company_id=:company_id AND order_id=:order_id AND status='reserved'
            """
        ),
        {"company_id": company_id, "order_id": order_id},
    )
    financial_entry_id = uuid4()
    today = utc_now().date()
    await database.execute(
        text(
            """
            INSERT INTO financial_entries (
              id,company_id,account_id,category_id,created_by_user_id,
              description,entry_type,status,amount,due_date,competence_date,reference
            ) VALUES (
              :id,:company_id,:account_id,:category_id,:actor_user_id,
              :description,'income','pending',:amount,:due_date,:competence_date,:reference
            )
            """
        ),
        {
            "id": financial_entry_id,
            "company_id": company_id,
            "account_id": payload.account_id,
            "category_id": payload.category_id,
            "actor_user_id": actor_user_id,
            "description": f"Pedido {order.order_number}",
            "amount": order.total,
            "due_date": payload.due_date,
            "competence_date": today,
            "reference": order.order_number,
        },
    )
    if payload.create_contract:
        contract_id = uuid4()
        contract_number = f"CTR-{today:%Y%m%d}-{contract_id.hex[:8].upper()}"
        await database.execute(
            text(
                """
                INSERT INTO commerce_contracts (
                  id,company_id,order_id,account_id,contract_number,title,status,
                  starts_on,ends_on,total_value,terms,created_by_user_id
                ) VALUES (
                  :id,:company_id,:order_id,:account_id,:number,:title,'active',
                  :starts_on,:ends_on,:total_value,:terms,:actor_user_id
                )
                """
            ),
            {
                "id": contract_id,
                "company_id": company_id,
                "order_id": order_id,
                "account_id": order.account_id,
                "number": contract_number,
                "title": f"Contrato do pedido {order.order_number}",
                "starts_on": today,
                "ends_on": payload.contract_ends_on,
                "total_value": order.total,
                "terms": payload.terms,
                "actor_user_id": actor_user_id,
            },
        )
        if payload.billing_interval:
            period_end = next_period(today, payload.billing_interval)
            await database.execute(
                text(
                    """
                    INSERT INTO commerce_customer_subscriptions (
                      id,company_id,contract_id,account_id,status,billing_interval,
                      amount,current_period_start,current_period_end,next_billing_on
                    ) VALUES (
                      gen_random_uuid(),:company_id,:contract_id,:account_id,'active',
                      :interval,:amount,:period_start,:period_end,:period_end
                    )
                    """
                ),
                {
                    "company_id": company_id,
                    "contract_id": contract_id,
                    "account_id": order.account_id,
                    "interval": payload.billing_interval,
                    "amount": order.total,
                    "period_start": today,
                    "period_end": period_end,
                },
            )
    updated = (
        await database.execute(
            text(
                """
                UPDATE commerce_orders
                SET status='confirmed',financial_entry_id=:financial_entry_id,
                    confirmed_at=now(),updated_at=now()
                WHERE company_id=:company_id AND id=:order_id
                RETURNING *
                """
            ),
            {
                "financial_entry_id": financial_entry_id,
                "company_id": company_id,
                "order_id": order_id,
            },
        )
    ).one()
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="commerce.order.confirmed",
        target_type="commerce_order",
        target_id=order_id,
        details={
            "financial_entry_id": str(financial_entry_id),
            "reservation_count": len(reservations),
            "contract_created": payload.create_contract,
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="commerce.order.confirmed",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={
                "order_id": str(order_id),
                "financial_entry_id": str(financial_entry_id),
            },
        ),
    )
    await database.commit()
    return await _order_response(database, updated)


async def list_contracts(
    database: AsyncSession, *, company_id: UUID
) -> list[ContractResponse]:
    rows = (
        await database.execute(
            text(
                """
                SELECT contract.*, subscription.billing_interval,
                       subscription.next_billing_on
                FROM commerce_contracts AS contract
                LEFT JOIN commerce_customer_subscriptions AS subscription
                  ON subscription.contract_id=contract.id
                 AND subscription.company_id=contract.company_id
                WHERE contract.company_id=:company_id
                ORDER BY contract.created_at DESC
                """
            ),
            {"company_id": company_id},
        )
    ).all()
    return [
        ContractResponse(
            id=row.id,
            order_id=row.order_id,
            contract_number=row.contract_number,
            title=row.title,
            status=row.status,
            starts_on=row.starts_on,
            ends_on=row.ends_on,
            total_value=row.total_value,
            billing_interval=row.billing_interval,
            next_billing_on=row.next_billing_on,
        )
        for row in rows
    ]


async def change_order_status(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    order_id: UUID,
    action: str,
) -> OrderResponse:
    order = (
        await database.execute(
            text(
                """
                SELECT * FROM commerce_orders
                WHERE company_id=:company_id AND id=:order_id
                FOR UPDATE
                """
            ),
            {"company_id": company_id, "order_id": order_id},
        )
    ).one_or_none()
    if order is None:
        raise CommerceTransactionError("Pedido não encontrado.", status_code=404)
    if action == "cancel":
        if order.status not in {"draft", "reserved"}:
            raise CommerceTransactionError(
                "Somente pedidos não confirmados podem ser cancelados.", status_code=409
            )
        await database.execute(
            text(
                """
                UPDATE commerce_inventory_reservations
                SET status='released',released_at=now()
                WHERE company_id=:company_id AND order_id=:order_id
                  AND status='reserved'
                """
            ),
            {"company_id": company_id, "order_id": order_id},
        )
        target_status = "cancelled"
    elif action == "fulfill":
        if order.status != "confirmed":
            raise CommerceTransactionError(
                "Somente pedidos confirmados podem ser concluídos.", status_code=409
            )
        target_status = "fulfilled"
    else:
        raise CommerceTransactionError("Ação de pedido inválida.")
    updated = (
        await database.execute(
            text(
                """
                UPDATE commerce_orders
                SET status=:status,
                    fulfilled_at=CASE WHEN :status='fulfilled' THEN now() ELSE fulfilled_at END,
                    updated_at=now()
                WHERE company_id=:company_id AND id=:order_id
                RETURNING *
                """
            ),
            {
                "status": target_status,
                "company_id": company_id,
                "order_id": order_id,
            },
        )
    ).one()
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action=f"commerce.order.{target_status}",
        target_type="commerce_order",
        target_id=order_id,
        details={"previous_status": order.status},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=f"commerce.order.{target_status}",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={"order_id": str(order_id)},
        ),
    )
    await database.commit()
    return await _order_response(database, updated)
