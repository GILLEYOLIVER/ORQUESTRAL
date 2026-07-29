from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utc_now
from app.modules.authorization.service import record_authorization_audit
from app.modules.commerce.settlement_models import (
    CommerceCommission,
    CommerceCustomerCredit,
    CommercePaymentEvent,
    CommercePaymentIntent,
    CommerceReturn,
    CommerceReturnItem,
)
from app.modules.commerce.settlement_schemas import (
    CommissionCreate,
    PaymentIntentCreate,
    PaymentWebhook,
    ReturnCreate,
    ReturnReceive,
    SettlementOverview,
)
from app.modules.commerce.transaction_models import CommerceOrder, CommerceOrderItem
from app.modules.commerce.transaction_service import (
    CommerceTransactionError,
)
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.finance.models import FinancialEntry
from app.modules.inventory.models import InventoryBalance, InventoryMovement


class PaymentSecurityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderIntent:
    reference: str
    status: str


class PaymentProvider(Protocol):
    code: str

    async def create_intent(
        self, *, order_id: UUID, amount: Decimal, currency: str, idempotency_key: str
    ) -> ProviderIntent: ...


class ManualPaymentProvider:
    code = "manual"

    async def create_intent(
        self, *, order_id: UUID, amount: Decimal, currency: str, idempotency_key: str
    ) -> ProviderIntent:
        del amount, currency, idempotency_key
        return ProviderIntent(
            reference=f"manual-{order_id}-{uuid4().hex[:12]}", status="pending"
        )


class SandboxPaymentProvider(ManualPaymentProvider):
    code = "sandbox"


PROVIDERS: dict[str, PaymentProvider] = {
    "manual": ManualPaymentProvider(),
    "sandbox": SandboxPaymentProvider(),
}


def calculate_percentage(amount: Decimal, rate: Decimal) -> Decimal:
    return (amount * rate / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def webhook_signature(provider: str, raw_body: bytes, secret: str) -> str:
    message = provider.encode() + b"." + raw_body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_webhook_signature(provider: str, raw_body: bytes, supplied: str | None) -> None:
    env_name = f"PAYMENT_WEBHOOK_SECRET_{provider.upper().replace('-', '_')}"
    secret = os.getenv(env_name) or os.getenv("PAYMENT_WEBHOOK_SECRET")
    if not secret:
        raise PaymentSecurityError("Webhook de pagamento não configurado.")
    if not supplied:
        raise PaymentSecurityError("Assinatura do webhook ausente.")
    expected = webhook_signature(provider, raw_body, secret)
    normalized = supplied.removeprefix("sha256=").strip().lower()
    if not hmac.compare_digest(expected, normalized):
        raise PaymentSecurityError("Assinatura do webhook inválida.")


async def _lock_order(
    database: AsyncSession, *, company_id: UUID, order_id: UUID
) -> CommerceOrder:
    order = await database.scalar(
        select(CommerceOrder)
        .where(CommerceOrder.id == order_id, CommerceOrder.company_id == company_id)
        .with_for_update()
    )
    if order is None:
        raise CommerceTransactionError("Pedido não encontrado.", status_code=404)
    return order


async def settlement_overview(
    database: AsyncSession, *, company_id: UUID, order_id: UUID | None = None
) -> SettlementOverview:
    payments = select(CommercePaymentIntent).where(
        CommercePaymentIntent.company_id == company_id
    )
    returns = select(CommerceReturn).where(CommerceReturn.company_id == company_id)
    commissions = select(CommerceCommission).where(
        CommerceCommission.company_id == company_id
    )
    if order_id:
        payments = payments.where(CommercePaymentIntent.order_id == order_id)
        returns = returns.where(CommerceReturn.order_id == order_id)
        commissions = commissions.where(CommerceCommission.order_id == order_id)
    return SettlementOverview(
        payments=list(
            (
                await database.scalars(
                    payments.order_by(CommercePaymentIntent.created_at.desc()).limit(100)
                )
            ).all()
        ),
        returns=list(
            (
                await database.scalars(
                    returns.order_by(CommerceReturn.created_at.desc()).limit(100)
                )
            ).all()
        ),
        commissions=list(
            (
                await database.scalars(
                    commissions.order_by(CommerceCommission.created_at.desc()).limit(100)
                )
            ).all()
        ),
    )


async def create_payment_intent(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    order_id: UUID,
    payload: PaymentIntentCreate,
) -> CommercePaymentIntent:
    await database.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"commerce-payment:{company_id}:{payload.idempotency_key}"},
    )
    existing = await database.scalar(
        select(CommercePaymentIntent).where(
            CommercePaymentIntent.company_id == company_id,
            CommercePaymentIntent.idempotency_key == payload.idempotency_key,
        )
    )
    if existing:
        return existing
    order = await _lock_order(database, company_id=company_id, order_id=order_id)
    if order.status not in {"confirmed", "fulfilled"}:
        raise CommerceTransactionError(
            "O pagamento exige um pedido confirmado.", status_code=409
        )
    captured = Decimal(
        await database.scalar(
            select(func.coalesce(func.sum(CommercePaymentIntent.amount), 0)).where(
                CommercePaymentIntent.company_id == company_id,
                CommercePaymentIntent.order_id == order_id,
                CommercePaymentIntent.status == "captured",
            )
        )
        or 0
    )
    if captured >= order.total:
        raise CommerceTransactionError("O pedido já está integralmente pago.", status_code=409)
    pending = await database.scalar(
        select(CommercePaymentIntent).where(
            CommercePaymentIntent.company_id == company_id,
            CommercePaymentIntent.order_id == order_id,
            CommercePaymentIntent.status == "pending",
        )
    )
    if pending:
        raise CommerceTransactionError(
            "Já existe uma cobrança aguardando confirmação.", status_code=409
        )
    amount = order.total - captured
    provider = PROVIDERS[payload.provider]
    provider_intent = await provider.create_intent(
        order_id=order.id,
        amount=amount,
        currency=order.currency,
        idempotency_key=payload.idempotency_key,
    )
    payment = CommercePaymentIntent(
        company_id=company_id,
        order_id=order.id,
        provider=provider.code,
        provider_reference=provider_intent.reference,
        method_type=payload.method_type,
        method_last4=payload.method_last4,
        status=provider_intent.status,
        amount=amount,
        currency=order.currency,
        idempotency_key=payload.idempotency_key,
        created_by_user_id=actor_user_id,
    )
    database.add(payment)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="commerce.payment_intent.created",
        target_type="commerce_payment_intent",
        target_id=payment.id,
        details={"order_id": str(order.id), "provider": provider.code},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="commerce.payment.requested",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={
                "payment_intent_id": str(payment.id),
                "order_id": str(order.id),
                "amount": str(payment.amount),
                "currency": payment.currency,
            },
        ),
    )
    return payment


async def process_payment_webhook(
    database: AsyncSession,
    *,
    provider: str,
    payload: PaymentWebhook,
    raw_body: bytes,
) -> CommercePaymentIntent:
    if provider not in PROVIDERS:
        raise CommerceTransactionError("Provedor de pagamento desconhecido.", status_code=404)
    payment = await database.scalar(
        select(CommercePaymentIntent)
        .where(
            CommercePaymentIntent.id == payload.payment_intent_id,
            CommercePaymentIntent.company_id == payload.company_id,
            CommercePaymentIntent.provider == provider,
        )
        .with_for_update()
    )
    if payment is None:
        raise CommerceTransactionError("Cobrança não encontrada.", status_code=404)
    duplicate = await database.scalar(
        select(CommercePaymentEvent).where(
            CommercePaymentEvent.provider == provider,
            CommercePaymentEvent.provider_event_id == payload.provider_event_id,
        )
    )
    if duplicate:
        return payment
    if (
        payload.provider_reference
        and payload.provider_reference != payment.provider_reference
    ):
        raise CommerceTransactionError("Referência de pagamento divergente.", status_code=409)
    database.add(
        CommercePaymentEvent(
            company_id=payload.company_id,
            payment_intent_id=payment.id,
            provider=provider,
            provider_event_id=payload.provider_event_id,
            event_type=payload.event_type,
            payload_hash=hashlib.sha256(raw_body).hexdigest(),
        )
    )
    now = utc_now()
    if payload.event_type == "captured":
        payment.status = "captured"
        payment.captured_at = now
        order = await _lock_order(
            database, company_id=payload.company_id, order_id=payment.order_id
        )
        if order.financial_entry_id:
            entry = await database.scalar(
                select(FinancialEntry)
                .where(
                    FinancialEntry.id == order.financial_entry_id,
                    FinancialEntry.company_id == payload.company_id,
                )
                .with_for_update()
            )
            if entry:
                entry.status = "settled"
                entry.settled_at = now
                entry.payment_method = payment.method_type
                entry.reference = payment.provider_reference
    elif payload.event_type == "refunded":
        payment.status = "refunded"
    else:
        payment.status = payload.event_type
    await database.flush()
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=f"commerce.payment.{payload.event_type}",
            company_id=payload.company_id,
            classification="confidential",
            payload={
                "payment_intent_id": str(payment.id),
                "order_id": str(payment.order_id),
                "provider_event_id": payload.provider_event_id,
            },
        ),
    )
    return payment


async def create_return(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    order_id: UUID,
    payload: ReturnCreate,
) -> CommerceReturn:
    await database.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"commerce-return:{company_id}:{payload.idempotency_key}"},
    )
    existing = await database.scalar(
        select(CommerceReturn).where(
            CommerceReturn.company_id == company_id,
            CommerceReturn.idempotency_key == payload.idempotency_key,
        )
    )
    if existing:
        return existing
    order = await _lock_order(database, company_id=company_id, order_id=order_id)
    if order.status != "fulfilled":
        raise CommerceTransactionError(
            "A devolução exige um pedido concluído.", status_code=409
        )
    result = CommerceReturn(
        company_id=company_id,
        order_id=order.id,
        status="requested",
        reason=payload.reason,
        refund_amount=Decimal("0"),
        idempotency_key=payload.idempotency_key,
        created_by_user_id=actor_user_id,
    )
    database.add(result)
    await database.flush()
    refund_total = Decimal("0")
    for requested in payload.items:
        order_item = await database.scalar(
            select(CommerceOrderItem).where(
                CommerceOrderItem.id == requested.order_item_id,
                CommerceOrderItem.order_id == order.id,
                CommerceOrderItem.company_id == company_id,
            )
        )
        if order_item is None:
            raise CommerceTransactionError("Item do pedido não encontrado.", status_code=404)
        returned = Decimal(
            await database.scalar(
                select(func.coalesce(func.sum(CommerceReturnItem.quantity), 0))
                .join(CommerceReturn, CommerceReturn.id == CommerceReturnItem.return_id)
                .where(
                    CommerceReturnItem.company_id == company_id,
                    CommerceReturnItem.order_item_id == order_item.id,
                    CommerceReturn.status.in_(("requested", "received")),
                )
            )
            or 0
        )
        if requested.quantity > order_item.quantity - returned:
            raise CommerceTransactionError(
                "A quantidade devolvida excede a quantidade disponível.", status_code=409
            )
        line_refund = (
            order_item.line_total * requested.quantity / order_item.quantity
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        refund_total += line_refund
        database.add(
            CommerceReturnItem(
                company_id=company_id,
                return_id=result.id,
                order_item_id=order_item.id,
                quantity=requested.quantity,
                line_refund=line_refund,
            )
        )
    result.refund_amount = refund_total
    await database.flush()
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="commerce.return.requested",
        target_type="commerce_return",
        target_id=result.id,
        details={"order_id": str(order.id), "amount": str(refund_total)},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="commerce.return.requested",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={"return_id": str(result.id), "order_id": str(order.id)},
        ),
    )
    return result


async def receive_return(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    return_id: UUID,
    payload: ReturnReceive,
) -> CommerceReturn:
    result = await database.scalar(
        select(CommerceReturn)
        .where(CommerceReturn.id == return_id, CommerceReturn.company_id == company_id)
        .with_for_update()
    )
    if result is None:
        raise CommerceTransactionError("Devolução não encontrada.", status_code=404)
    if result.status == "received":
        return result
    if result.status != "requested":
        raise CommerceTransactionError("A devolução não pode ser recebida.", status_code=409)
    location = await database.scalar(
        text(
            "SELECT 1 FROM inventory_locations "
            "WHERE id = :location_id AND company_id = :company_id"
        ),
        {"location_id": payload.stock_location_id, "company_id": company_id},
    )
    if not location:
        raise CommerceTransactionError("Local de estoque não encontrado.", status_code=404)
    lines = list(
        (
            await database.scalars(
                select(CommerceReturnItem).where(
                    CommerceReturnItem.return_id == result.id,
                    CommerceReturnItem.company_id == company_id,
                )
            )
        ).all()
    )
    for line in lines:
        item = await database.scalar(
            select(CommerceOrderItem).where(
                CommerceOrderItem.id == line.order_item_id,
                CommerceOrderItem.company_id == company_id,
            )
        )
        if item is None:
            raise CommerceTransactionError("Item original não encontrado.", status_code=409)
        balance = await database.scalar(
            select(InventoryBalance)
            .where(
                InventoryBalance.company_id == company_id,
                InventoryBalance.item_id == item.inventory_item_id,
                InventoryBalance.location_id == payload.stock_location_id,
            )
            .with_for_update()
        )
        previous = balance.quantity if balance else Decimal("0")
        resulting = previous + line.quantity
        if balance:
            balance.quantity = resulting
            balance.updated_at = utc_now()
        else:
            database.add(
                InventoryBalance(
                    company_id=company_id,
                    item_id=item.inventory_item_id,
                    location_id=payload.stock_location_id,
                    quantity=resulting,
                )
            )
        database.add(
            InventoryMovement(
                company_id=company_id,
                item_id=item.inventory_item_id,
                location_id=payload.stock_location_id,
                created_by_user_id=actor_user_id,
                movement_type="in",
                quantity=line.quantity,
                previous_quantity=previous,
                resulting_quantity=resulting,
                reason="Devolução comercial recebida",
                reference=f"return:{result.id}",
                occurred_at=utc_now(),
            )
        )
    today = date.today()
    financial_entry = FinancialEntry(
        company_id=company_id,
        created_by_user_id=actor_user_id,
        description=f"Crédito da devolução {result.id}",
        notes="Gerado automaticamente pelo fluxo comercial governado.",
        entry_type="expense",
        status="pending",
        amount=result.refund_amount,
        due_date=today,
        competence_date=today,
        payment_method="customer_credit" if payload.resolution == "credit" else "refund",
        reference=f"return:{result.id}",
    )
    database.add(financial_entry)
    await database.flush()
    order = await _lock_order(database, company_id=company_id, order_id=result.order_id)
    credit = CommerceCustomerCredit(
        company_id=company_id,
        order_id=result.order_id,
        return_id=result.id,
        financial_entry_id=financial_entry.id,
        amount=result.refund_amount,
        currency=order.currency,
        status="issued" if payload.resolution == "credit" else "refund_pending",
        created_by_user_id=actor_user_id,
    )
    database.add(credit)
    result.status = "received"
    result.resolution = payload.resolution
    result.stock_location_id = payload.stock_location_id
    result.received_by_user_id = actor_user_id
    result.received_at = utc_now()
    await database.flush()
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="commerce.return.received",
        target_type="commerce_return",
        target_id=result.id,
        details={"resolution": payload.resolution, "credit_id": str(credit.id)},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="commerce.return.received",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={
                "return_id": str(result.id),
                "order_id": str(result.order_id),
                "credit_id": str(credit.id),
            },
        ),
    )
    return result


async def accrue_commission(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    order_id: UUID,
    payload: CommissionCreate,
) -> CommerceCommission:
    await database.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"commerce-commission:{company_id}:{payload.idempotency_key}"},
    )
    existing = await database.scalar(
        select(CommerceCommission).where(
            CommerceCommission.company_id == company_id,
            CommerceCommission.idempotency_key == payload.idempotency_key,
        )
    )
    if existing:
        return existing
    order = await _lock_order(database, company_id=company_id, order_id=order_id)
    if order.status != "fulfilled":
        raise CommerceTransactionError(
            "A comissão exige um pedido concluído.", status_code=409
        )
    membership = await database.scalar(
        text(
            "SELECT 1 FROM company_users WHERE company_id = :company_id "
            "AND user_id = :user_id AND status = 'active'"
        ),
        {"company_id": company_id, "user_id": payload.beneficiary_user_id},
    )
    if not membership:
        raise CommerceTransactionError(
            "O beneficiário não pertence à empresa.", status_code=409
        )
    commission = CommerceCommission(
        company_id=company_id,
        order_id=order.id,
        beneficiary_user_id=payload.beneficiary_user_id,
        rate=payload.rate,
        amount=calculate_percentage(order.total, payload.rate),
        currency=order.currency,
        status="accrued",
        idempotency_key=payload.idempotency_key,
        created_by_user_id=actor_user_id,
    )
    database.add(commission)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="commerce.commission.accrued",
        target_type="commerce_commission",
        target_id=commission.id,
        details={"order_id": str(order.id), "beneficiary": str(payload.beneficiary_user_id)},
    )
    return commission


async def approve_commission(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    commission_id: UUID,
) -> CommerceCommission:
    commission = await database.scalar(
        select(CommerceCommission)
        .where(
            CommerceCommission.id == commission_id,
            CommerceCommission.company_id == company_id,
        )
        .with_for_update()
    )
    if commission is None:
        raise CommerceTransactionError("Comissão não encontrada.", status_code=404)
    if commission.status == "approved":
        return commission
    if commission.status != "accrued":
        raise CommerceTransactionError("A comissão não pode ser aprovada.", status_code=409)
    today = date.today()
    entry = FinancialEntry(
        company_id=company_id,
        created_by_user_id=actor_user_id,
        description=f"Comissão comercial do pedido {commission.order_id}",
        notes=f"Beneficiário: {commission.beneficiary_user_id}",
        entry_type="expense",
        status="pending",
        amount=commission.amount,
        due_date=today,
        competence_date=today,
        payment_method="commission",
        reference=f"commission:{commission.id}",
    )
    database.add(entry)
    await database.flush()
    commission.financial_entry_id = entry.id
    commission.status = "approved"
    commission.approved_by_user_id = actor_user_id
    commission.approved_at = utc_now()
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="commerce.commission.approved",
        target_type="commerce_commission",
        target_id=commission.id,
        details={"financial_entry_id": str(entry.id)},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="commerce.commission.approved",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={
                "commission_id": str(commission.id),
                "order_id": str(commission.order_id),
                "amount": str(commission.amount),
            },
        ),
    )
    return commission
