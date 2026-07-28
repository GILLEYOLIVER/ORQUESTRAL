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
