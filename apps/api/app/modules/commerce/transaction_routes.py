from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.commerce.transaction_schemas import (
    ContractResponse,
    OrderConfirm,
    OrderFromQuoteCreate,
    OrderReserve,
    OrderResponse,
)
from app.modules.commerce.transaction_service import (
    CommerceTransactionError,
    change_order_status,
    confirm_order,
    create_order_from_quote,
    list_contracts,
    list_orders,
    reserve_order,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(
    prefix="/commerce",
    tags=["commerce-transactions"],
    dependencies=[Depends(require_active_module("commerce"))],
)
CanView = Annotated[Principal, Depends(require_permission("commerce.view"))]
CanManageOrders = Annotated[
    Principal, Depends(require_permission("commerce.orders.manage"))
]
CanConfirmOrders = Annotated[
    Principal, Depends(require_permission("commerce.orders.confirm"))
]
CanViewContracts = Annotated[
    Principal, Depends(require_permission("commerce.contracts.view"))
]


def _raise(error: CommerceTransactionError) -> NoReturn:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/orders", response_model=list[OrderResponse])
async def orders(
    principal: CanView, database: DatabaseSession
) -> list[OrderResponse]:
    context = get_request_context(principal)
    return await list_orders(database, company_id=context.company_id)


@router.post(
    "/orders/from-quote",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def order_from_quote(
    payload: OrderFromQuoteCreate,
    principal: CanManageOrders,
    database: DatabaseSession,
) -> OrderResponse:
    context = get_request_context(principal)
    try:
        return await create_order_from_quote(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except CommerceTransactionError as error:
        _raise(error)


@router.post("/orders/{order_id}/reserve", response_model=OrderResponse)
async def reserve(
    order_id: UUID,
    payload: OrderReserve,
    principal: CanManageOrders,
    database: DatabaseSession,
) -> OrderResponse:
    context = get_request_context(principal)
    try:
        return await reserve_order(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            order_id=order_id,
            location_id=payload.location_id,
        )
    except CommerceTransactionError as error:
        _raise(error)


@router.post("/orders/{order_id}/confirm", response_model=OrderResponse)
async def confirm(
    order_id: UUID,
    payload: OrderConfirm,
    principal: CanConfirmOrders,
    database: DatabaseSession,
) -> OrderResponse:
    context = get_request_context(principal)
    try:
        return await confirm_order(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            order_id=order_id,
            payload=payload,
        )
    except CommerceTransactionError as error:
        _raise(error)


@router.get("/contracts", response_model=list[ContractResponse])
async def contracts(
    principal: CanViewContracts, database: DatabaseSession
) -> list[ContractResponse]:
    context = get_request_context(principal)
    return await list_contracts(database, company_id=context.company_id)


@router.post("/orders/{order_id}/cancel", response_model=OrderResponse)
async def cancel(
    order_id: UUID,
    principal: CanManageOrders,
    database: DatabaseSession,
) -> OrderResponse:
    context = get_request_context(principal)
    try:
        return await change_order_status(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            order_id=order_id,
            action="cancel",
        )
    except CommerceTransactionError as error:
        _raise(error)


@router.post("/orders/{order_id}/fulfill", response_model=OrderResponse)
async def fulfill(
    order_id: UUID,
    principal: CanConfirmOrders,
    database: DatabaseSession,
) -> OrderResponse:
    context = get_request_context(principal)
    try:
        return await change_order_status(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            order_id=order_id,
            action="fulfill",
        )
    except CommerceTransactionError as error:
        _raise(error)


from fastapi import Header, Request  # noqa: E402

from app.modules.commerce.settlement_schemas import (  # noqa: E402
    CommissionCreate,
    CommissionResponse,
    PaymentIntentCreate,
    PaymentIntentResponse,
    PaymentWebhook,
    ReturnCreate,
    ReturnReceive,
    ReturnResponse,
    SettlementOverview,
)
from app.modules.commerce.settlement_service import (  # noqa: E402
    PaymentSecurityError,
    accrue_commission,
    approve_commission,
    create_payment_intent,
    create_return,
    process_payment_webhook,
    receive_return,
    settlement_overview,
    verify_webhook_signature,
)


@router.get("/settlement", response_model=SettlementOverview)
async def settlement(
    principal: CanView,
    database: DatabaseSession,
    order_id: UUID | None = None,
) -> SettlementOverview:
    context = get_request_context(principal)
    return await settlement_overview(
        database, company_id=context.company_id, order_id=order_id
    )


@router.post(
    "/orders/{order_id}/payment-intents",
    response_model=PaymentIntentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def payment_intent(
    order_id: UUID,
    payload: PaymentIntentCreate,
    principal: CanConfirmOrders,
    database: DatabaseSession,
) -> PaymentIntentResponse:
    context = get_request_context(principal)
    try:
        return PaymentIntentResponse.model_validate(
            await create_payment_intent(
                database,
                company_id=context.company_id,
                actor_user_id=context.user_id,
                order_id=order_id,
                payload=payload,
            )
        )
    except CommerceTransactionError as error:
        _raise(error)


@router.post(
    "/payments/webhooks/{provider}",
    response_model=PaymentIntentResponse,
)
async def payment_webhook(
    provider: str,
    payload: PaymentWebhook,
    request: Request,
    database: DatabaseSession,
    signature: str | None = Header(default=None, alias="X-Orkestral-Signature"),
) -> PaymentIntentResponse:
    raw_body = await request.body()
    try:
        verify_webhook_signature(provider, raw_body, signature)
        return PaymentIntentResponse.model_validate(
            await process_payment_webhook(
                database, provider=provider, payload=payload, raw_body=raw_body
            )
        )
    except PaymentSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)
        ) from error
    except CommerceTransactionError as error:
        _raise(error)


@router.post(
    "/orders/{order_id}/returns",
    response_model=ReturnResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_return(
    order_id: UUID,
    payload: ReturnCreate,
    principal: CanManageOrders,
    database: DatabaseSession,
) -> ReturnResponse:
    context = get_request_context(principal)
    try:
        return ReturnResponse.model_validate(
            await create_return(
                database,
                company_id=context.company_id,
                actor_user_id=context.user_id,
                order_id=order_id,
                payload=payload,
            )
        )
    except CommerceTransactionError as error:
        _raise(error)


@router.post("/returns/{return_id}/receive", response_model=ReturnResponse)
async def return_received(
    return_id: UUID,
    payload: ReturnReceive,
    principal: CanConfirmOrders,
    database: DatabaseSession,
) -> ReturnResponse:
    context = get_request_context(principal)
    try:
        return ReturnResponse.model_validate(
            await receive_return(
                database,
                company_id=context.company_id,
                actor_user_id=context.user_id,
                return_id=return_id,
                payload=payload,
            )
        )
    except CommerceTransactionError as error:
        _raise(error)


@router.post(
    "/orders/{order_id}/commissions",
    response_model=CommissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def commission(
    order_id: UUID,
    payload: CommissionCreate,
    principal: CanConfirmOrders,
    database: DatabaseSession,
) -> CommissionResponse:
    context = get_request_context(principal)
    try:
        return CommissionResponse.model_validate(
            await accrue_commission(
                database,
                company_id=context.company_id,
                actor_user_id=context.user_id,
                order_id=order_id,
                payload=payload,
            )
        )
    except CommerceTransactionError as error:
        _raise(error)


@router.post(
    "/commissions/{commission_id}/approve",
    response_model=CommissionResponse,
)
async def commission_approved(
    commission_id: UUID,
    principal: CanConfirmOrders,
    database: DatabaseSession,
) -> CommissionResponse:
    context = get_request_context(principal)
    try:
        return CommissionResponse.model_validate(
            await approve_commission(
                database,
                company_id=context.company_id,
                actor_user_id=context.user_id,
                commission_id=commission_id,
            )
        )
    except CommerceTransactionError as error:
        _raise(error)
