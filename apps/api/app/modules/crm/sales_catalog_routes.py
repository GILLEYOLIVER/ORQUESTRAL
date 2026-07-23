from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.crm.sales_catalog_schemas import (
    PriceBookCreate,
    PriceBookEntryUpsert,
    PriceBookResponse,
    QuoteCreate,
    QuoteDecision,
    QuoteResponse,
)
from app.modules.crm.sales_catalog_service import (
    SalesCatalogError,
    create_price_book,
    create_quote,
    decide_quote,
    list_price_books,
    list_quotes,
    publish_price_book,
    publish_quote,
    upsert_price_book_entry,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(prefix="/crm/sales", tags=["crm-sales-catalog"])

ActiveCRM = Annotated[Principal, Depends(require_active_module("crm"))]
CanViewCatalog = Annotated[Principal, Depends(require_permission("crm.catalog.view"))]
CanManageCatalog = Annotated[Principal, Depends(require_permission("crm.catalog.manage"))]
CanViewQuotes = Annotated[Principal, Depends(require_permission("crm.quotes.view"))]
CanManageQuotes = Annotated[Principal, Depends(require_permission("crm.quotes.manage"))]
CanPublishQuotes = Annotated[Principal, Depends(require_permission("crm.quotes.publish"))]


def _raise(error: SalesCatalogError) -> NoReturn:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/price-books", response_model=list[PriceBookResponse])
async def price_books(
    principal: CanViewCatalog, _: ActiveCRM, database: DatabaseSession
) -> list[PriceBookResponse]:
    context = get_request_context(principal)
    return await list_price_books(database, company_id=context.company_id)


@router.post(
    "/price-books", response_model=PriceBookResponse, status_code=status.HTTP_201_CREATED
)
async def add_price_book(
    payload: PriceBookCreate,
    principal: CanManageCatalog,
    _: ActiveCRM,
    database: DatabaseSession,
) -> PriceBookResponse:
    context = get_request_context(principal)
    try:
        return await create_price_book(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except SalesCatalogError as error:
        _raise(error)


@router.put(
    "/price-books/{price_book_id}/entries", response_model=PriceBookResponse
)
async def set_price(
    price_book_id: UUID,
    payload: PriceBookEntryUpsert,
    principal: CanManageCatalog,
    _: ActiveCRM,
    database: DatabaseSession,
) -> PriceBookResponse:
    context = get_request_context(principal)
    try:
        return await upsert_price_book_entry(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            price_book_id=price_book_id,
            payload=payload,
        )
    except SalesCatalogError as error:
        _raise(error)


@router.post(
    "/price-books/{price_book_id}/publish", response_model=PriceBookResponse
)
async def publish_prices(
    price_book_id: UUID,
    principal: CanManageCatalog,
    _: ActiveCRM,
    database: DatabaseSession,
) -> PriceBookResponse:
    context = get_request_context(principal)
    try:
        return await publish_price_book(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            price_book_id=price_book_id,
        )
    except SalesCatalogError as error:
        _raise(error)


@router.get("/quotes", response_model=list[QuoteResponse])
async def quotes(
    principal: CanViewQuotes, _: ActiveCRM, database: DatabaseSession
) -> list[QuoteResponse]:
    context = get_request_context(principal)
    return await list_quotes(database, company_id=context.company_id)


@router.post(
    "/quotes", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED
)
async def add_quote(
    payload: QuoteCreate,
    principal: CanManageQuotes,
    _: ActiveCRM,
    database: DatabaseSession,
) -> QuoteResponse:
    context = get_request_context(principal)
    try:
        return await create_quote(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except SalesCatalogError as error:
        _raise(error)


@router.post("/quotes/{quote_id}/publish", response_model=QuoteResponse)
async def publish_proposal(
    quote_id: UUID,
    principal: CanPublishQuotes,
    _: ActiveCRM,
    database: DatabaseSession,
) -> QuoteResponse:
    context = get_request_context(principal)
    try:
        return await publish_quote(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            quote_id=quote_id,
        )
    except SalesCatalogError as error:
        _raise(error)


@router.post("/quotes/{quote_id}/decision", response_model=QuoteResponse)
async def decide_proposal(
    quote_id: UUID,
    payload: QuoteDecision,
    principal: CanPublishQuotes,
    _: ActiveCRM,
    database: DatabaseSession,
) -> QuoteResponse:
    context = get_request_context(principal)
    try:
        return await decide_quote(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            quote_id=quote_id,
            payload=payload,
        )
    except SalesCatalogError as error:
        _raise(error)
