from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.finance.models import FinancialAccount, FinancialCategory, FinancialEntry
from app.modules.finance.schemas import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    CategoryCreate,
    CategoryResponse,
    EntryCreate,
    EntryResponse,
    EntrySettle,
    EntryUpdate,
    FinanceSummaryResponse,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(
    prefix="/finance",
    tags=["finance"],
    dependencies=[Depends(require_active_module("finance"))],
)
CanViewFinance = Annotated[Principal, Depends(require_permission("finance.view"))]
CanManageAccounts = Annotated[Principal, Depends(require_permission("finance.accounts.manage"))]
CanCreateEntries = Annotated[Principal, Depends(require_permission("finance.entries.create"))]
CanUpdateEntries = Annotated[Principal, Depends(require_permission("finance.entries.update"))]
CanSettleEntries = Annotated[Principal, Depends(require_permission("finance.entries.settle"))]
CanManageCategories = Annotated[Principal, Depends(require_permission("finance.categories.manage"))]


async def _account(
    database: DatabaseSession, *, account_id: UUID, company_id: UUID, active_only: bool = True
) -> FinancialAccount:
    statement = select(FinancialAccount).where(
        FinancialAccount.id == account_id,
        FinancialAccount.company_id == company_id,
    )
    if active_only:
        statement = statement.where(FinancialAccount.active.is_(True))
    account = await database.scalar(statement)
    if account is None:
        raise HTTPException(status_code=404, detail="Conta financeira nao encontrada.")
    return account


async def _account_response(
    database: DatabaseSession, account: FinancialAccount
) -> AccountResponse:
    movement = Decimal(
        await database.scalar(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (FinancialEntry.entry_type == "income", FinancialEntry.amount),
                            else_=-FinancialEntry.amount,
                        )
                    ),
                    0,
                )
            ).where(
                FinancialEntry.company_id == account.company_id,
                FinancialEntry.account_id == account.id,
                FinancialEntry.status == "settled",
            )
        )
        or 0
    )
    return AccountResponse.model_validate(
        {
            "id": account.id,
            "name": account.name,
            "account_type": account.account_type,
            "opening_balance": account.opening_balance,
            "current_balance": account.opening_balance + movement,
            "active": account.active,
            "created_at": account.created_at,
            "updated_at": account.updated_at,
        }
    )


async def _entry(database: DatabaseSession, *, entry_id: UUID, company_id: UUID) -> FinancialEntry:
    entry = await database.scalar(
        select(FinancialEntry).where(
            FinancialEntry.id == entry_id,
            FinancialEntry.company_id == company_id,
        )
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Lancamento financeiro nao encontrado.")
    return entry


def _entry_response(entry: FinancialEntry) -> EntryResponse:
    return EntryResponse.model_validate(
        {
            "id": entry.id,
            "account_id": entry.account_id,
            "category_id": entry.category_id,
            "description": entry.description,
            "notes": entry.notes,
            "entry_type": entry.entry_type,
            "status": entry.status,
            "amount": entry.amount,
            "due_date": entry.due_date,
            "competence_date": entry.competence_date,
            "settled_at": entry.settled_at,
            "payment_method": entry.payment_method,
            "reference": entry.reference,
            "overdue": entry.status == "pending" and entry.due_date < date.today(),
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
        }
    )


async def _validate_category(
    database: DatabaseSession,
    *,
    category_id: UUID | None,
    company_id: UUID,
    entry_type: str,
) -> None:
    if category_id is None:
        return
    category = await database.scalar(
        select(FinancialCategory).where(
            FinancialCategory.id == category_id,
            FinancialCategory.company_id == company_id,
            FinancialCategory.entry_type == entry_type,
            FinancialCategory.active.is_(True),
        )
    )
    if category is None:
        raise HTTPException(
            status_code=404,
            detail="Categoria ativa e compatível com o tipo do lancamento nao encontrada.",
        )


@router.get("/summary", response_model=FinanceSummaryResponse)
async def finance_summary(
    principal: CanViewFinance, database: DatabaseSession
) -> FinanceSummaryResponse:
    context = get_request_context(principal)
    today = date.today()
    month_start = today.replace(day=1)
    opening = Decimal(
        await database.scalar(
            select(func.coalesce(func.sum(FinancialAccount.opening_balance), 0)).where(
                FinancialAccount.company_id == context.company_id,
                FinancialAccount.active.is_(True),
            )
        )
        or 0
    )
    settled_net = Decimal(
        await database.scalar(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (FinancialEntry.entry_type == "income", FinancialEntry.amount),
                            else_=-FinancialEntry.amount,
                        )
                    ),
                    0,
                )
            ).where(
                FinancialEntry.company_id == context.company_id,
                FinancialEntry.status == "settled",
            )
        )
        or 0
    )

    async def total_for(
        *, entry_type: str, entry_status: str, from_date: date | None = None
    ) -> Decimal:
        statement = select(func.coalesce(func.sum(FinancialEntry.amount), 0)).where(
            FinancialEntry.company_id == context.company_id,
            FinancialEntry.entry_type == entry_type,
            FinancialEntry.status == entry_status,
        )
        if from_date is not None:
            statement = statement.where(FinancialEntry.competence_date >= from_date)
        return Decimal(await database.scalar(statement) or 0)

    receivable_pending = await total_for(entry_type="income", entry_status="pending")
    payable_pending = await total_for(entry_type="expense", entry_status="pending")
    income_month = await total_for(
        entry_type="income", entry_status="settled", from_date=month_start
    )
    expense_month = await total_for(
        entry_type="expense", entry_status="settled", from_date=month_start
    )
    overdue_total, overdue_count = (
        await database.execute(
            select(
                func.coalesce(func.sum(FinancialEntry.amount), 0),
                func.count(FinancialEntry.id),
            ).where(
                FinancialEntry.company_id == context.company_id,
                FinancialEntry.status == "pending",
                FinancialEntry.due_date < today,
            )
        )
    ).one()
    return FinanceSummaryResponse(
        current_balance=opening + settled_net,
        receivable_pending=receivable_pending,
        payable_pending=payable_pending,
        income_month=income_month,
        expense_month=expense_month,
        overdue_total=Decimal(overdue_total or 0),
        overdue_count=int(overdue_count or 0),
    )


@router.get("/accounts", response_model=list[AccountResponse])
async def list_accounts(
    principal: CanViewFinance, database: DatabaseSession
) -> list[AccountResponse]:
    context = get_request_context(principal)
    rows = list(
        await database.scalars(
            select(FinancialAccount)
            .where(FinancialAccount.company_id == context.company_id)
            .order_by(FinancialAccount.active.desc(), FinancialAccount.name)
        )
    )
    return [await _account_response(database, row) for row in rows]


@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AccountCreate, principal: CanManageAccounts, database: DatabaseSession
) -> AccountResponse:
    context = get_request_context(principal)
    account = FinancialAccount(
        company_id=context.company_id,
        name=payload.name.strip(),
        account_type=payload.account_type,
        opening_balance=payload.opening_balance,
    )
    database.add(account)
    await database.commit()
    await database.refresh(account)
    return await _account_response(database, account)


@router.patch("/accounts/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: UUID,
    payload: AccountUpdate,
    principal: CanManageAccounts,
    database: DatabaseSession,
) -> AccountResponse:
    context = get_request_context(principal)
    account = await _account(
        database, account_id=account_id, company_id=context.company_id, active_only=False
    )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value.strip() if field == "name" and value else value)
    account.updated_at = utc_now()
    await database.commit()
    await database.refresh(account)
    return await _account_response(database, account)


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(
    principal: CanViewFinance, database: DatabaseSession
) -> list[CategoryResponse]:
    context = get_request_context(principal)
    rows = list(
        await database.scalars(
            select(FinancialCategory)
            .where(
                FinancialCategory.company_id == context.company_id,
                FinancialCategory.active.is_(True),
            )
            .order_by(FinancialCategory.entry_type, FinancialCategory.name)
        )
    )
    return [CategoryResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate, principal: CanManageCategories, database: DatabaseSession
) -> CategoryResponse:
    context = get_request_context(principal)
    category = FinancialCategory(
        company_id=context.company_id,
        name=payload.name.strip(),
        entry_type=payload.entry_type,
    )
    database.add(category)
    await database.commit()
    await database.refresh(category)
    return CategoryResponse.model_validate(category, from_attributes=True)


@router.get("/entries", response_model=list[EntryResponse])
async def list_entries(
    principal: CanViewFinance,
    database: DatabaseSession,
    entry_status: str | None = Query(default=None, alias="status"),
    entry_type: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[EntryResponse]:
    context = get_request_context(principal)
    statement = select(FinancialEntry).where(FinancialEntry.company_id == context.company_id)
    if entry_status:
        statement = statement.where(FinancialEntry.status == entry_status)
    if entry_type:
        statement = statement.where(FinancialEntry.entry_type == entry_type)
    rows = list(
        await database.scalars(
            statement.order_by(
                FinancialEntry.due_date.desc(), FinancialEntry.created_at.desc()
            ).limit(limit)
        )
    )
    return [_entry_response(row) for row in rows]


@router.post("/entries", response_model=EntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(
    payload: EntryCreate, principal: CanCreateEntries, database: DatabaseSession
) -> EntryResponse:
    context = get_request_context(principal)
    await _validate_category(
        database,
        category_id=payload.category_id,
        company_id=context.company_id,
        entry_type=payload.entry_type,
    )
    values = payload.model_dump()
    values["competence_date"] = payload.competence_date or payload.due_date
    entry = FinancialEntry(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **values,
    )
    entry.description = entry.description.strip()
    database.add(entry)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="finance.entry.created",
        target_type="financial_entry",
        target_id=entry.id,
        details={"entry_type": entry.entry_type, "amount": str(entry.amount)},
    )
    await database.commit()
    await database.refresh(entry)
    return _entry_response(entry)


@router.patch("/entries/{entry_id}", response_model=EntryResponse)
async def update_entry(
    entry_id: UUID,
    payload: EntryUpdate,
    principal: CanUpdateEntries,
    database: DatabaseSession,
) -> EntryResponse:
    context = get_request_context(principal)
    entry = await _entry(database, entry_id=entry_id, company_id=context.company_id)
    if entry.status != "pending":
        raise HTTPException(
            status_code=409, detail="Somente lancamentos pendentes podem ser editados."
        )
    await _validate_category(
        database,
        category_id=payload.category_id
        if "category_id" in payload.model_fields_set
        else entry.category_id,
        company_id=context.company_id,
        entry_type=entry.entry_type,
    )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    entry.updated_at = utc_now()
    await database.commit()
    await database.refresh(entry)
    return _entry_response(entry)


@router.post("/entries/{entry_id}/settle", response_model=EntryResponse)
async def settle_entry(
    entry_id: UUID,
    payload: EntrySettle,
    principal: CanSettleEntries,
    database: DatabaseSession,
) -> EntryResponse:
    context = get_request_context(principal)
    entry = await _entry(database, entry_id=entry_id, company_id=context.company_id)
    if entry.status != "pending":
        raise HTTPException(status_code=409, detail="O lancamento nao esta pendente.")
    await _account(database, account_id=payload.account_id, company_id=context.company_id)
    entry.account_id = payload.account_id
    entry.status = "settled"
    entry.settled_at = payload.settled_at or datetime.now(UTC)
    entry.payment_method = payload.payment_method
    entry.updated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="finance.entry.settled",
        target_type="financial_entry",
        target_id=entry.id,
        details={"account_id": str(payload.account_id), "amount": str(entry.amount)},
    )
    await database.commit()
    await database.refresh(entry)
    return _entry_response(entry)


@router.post("/entries/{entry_id}/cancel", response_model=EntryResponse)
async def cancel_entry(
    entry_id: UUID, principal: CanUpdateEntries, database: DatabaseSession
) -> EntryResponse:
    context = get_request_context(principal)
    entry = await _entry(database, entry_id=entry_id, company_id=context.company_id)
    if entry.status != "pending":
        raise HTTPException(
            status_code=409, detail="Somente lancamentos pendentes podem ser cancelados."
        )
    entry.status = "cancelled"
    entry.updated_at = utc_now()
    await database.commit()
    await database.refresh(entry)
    return _entry_response(entry)
