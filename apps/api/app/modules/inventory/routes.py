from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.inventory.models import (
    InventoryBalance,
    InventoryCategory,
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
)
from app.modules.inventory.schemas import (
    BalanceResponse,
    CategoryCreate,
    CategoryResponse,
    InventorySummaryResponse,
    ItemCreate,
    ItemResponse,
    ItemUpdate,
    LocationCreate,
    LocationResponse,
    LocationUpdate,
    MovementCreate,
    MovementResponse,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(require_active_module("inventory"))],
)
CanViewInventory = Annotated[Principal, Depends(require_permission("inventory.view"))]
CanManageItems = Annotated[Principal, Depends(require_permission("inventory.items.manage"))]
CanCreateMovements = Annotated[Principal, Depends(require_permission("inventory.movements.create"))]
CanManageLocations = Annotated[Principal, Depends(require_permission("inventory.locations.manage"))]
CanManageCategories = Annotated[
    Principal, Depends(require_permission("inventory.categories.manage"))
]


async def _item(database: DatabaseSession, *, item_id: UUID, company_id: UUID) -> InventoryItem:
    item = await database.scalar(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.company_id == company_id,
            InventoryItem.archived_at.is_(None),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Item nao encontrado nesta empresa.")
    return item


async def _location(
    database: DatabaseSession, *, location_id: UUID, company_id: UUID
) -> InventoryLocation:
    location = await database.scalar(
        select(InventoryLocation).where(
            InventoryLocation.id == location_id,
            InventoryLocation.company_id == company_id,
            InventoryLocation.active.is_(True),
        )
    )
    if location is None:
        raise HTTPException(status_code=404, detail="Local de estoque ativo nao encontrado.")
    return location


async def _item_response(database: DatabaseSession, item: InventoryItem) -> ItemResponse:
    total = Decimal(
        await database.scalar(
            select(func.coalesce(func.sum(InventoryBalance.quantity), 0)).where(
                InventoryBalance.company_id == item.company_id,
                InventoryBalance.item_id == item.id,
            )
        )
        or 0
    )
    return ItemResponse.model_validate(
        {
            "id": item.id,
            "sku": item.sku,
            "name": item.name,
            "description": item.description,
            "category_id": item.category_id,
            "unit": item.unit,
            "minimum_stock": item.minimum_stock,
            "total_quantity": total,
            "low_stock": item.minimum_stock > 0 and total <= item.minimum_stock,
            "active": item.active,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
    )


@router.get("/summary", response_model=InventorySummaryResponse)
async def inventory_summary(
    principal: CanViewInventory, database: DatabaseSession
) -> InventorySummaryResponse:
    context = get_request_context(principal)
    items = list(
        await database.scalars(
            select(InventoryItem).where(
                InventoryItem.company_id == context.company_id,
                InventoryItem.archived_at.is_(None),
                InventoryItem.active.is_(True),
            )
        )
    )
    responses = [await _item_response(database, item) for item in items]
    locations_total = int(
        await database.scalar(
            select(func.count(InventoryLocation.id)).where(
                InventoryLocation.company_id == context.company_id,
                InventoryLocation.active.is_(True),
            )
        )
        or 0
    )
    return InventorySummaryResponse(
        items_total=len(items),
        locations_total=locations_total,
        low_stock_total=sum(1 for item in responses if item.low_stock),
        total_quantity=sum((item.total_quantity for item in responses), Decimal("0")),
    )


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(
    principal: CanViewInventory, database: DatabaseSession
) -> list[CategoryResponse]:
    context = get_request_context(principal)
    rows = list(
        await database.scalars(
            select(InventoryCategory)
            .where(
                InventoryCategory.company_id == context.company_id,
                InventoryCategory.active.is_(True),
            )
            .order_by(InventoryCategory.name)
        )
    )
    return [CategoryResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate, principal: CanManageCategories, database: DatabaseSession
) -> CategoryResponse:
    context = get_request_context(principal)
    existing = await database.scalar(
        select(InventoryCategory.id).where(
            InventoryCategory.company_id == context.company_id,
            func.lower(InventoryCategory.name) == payload.name.strip().lower(),
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Ja existe uma categoria com este nome.")
    category = InventoryCategory(
        company_id=context.company_id,
        name=payload.name.strip(),
        description=payload.description,
    )
    database.add(category)
    await database.commit()
    await database.refresh(category)
    return CategoryResponse.model_validate(category, from_attributes=True)


@router.get("/locations", response_model=list[LocationResponse])
async def list_locations(
    principal: CanViewInventory, database: DatabaseSession
) -> list[LocationResponse]:
    context = get_request_context(principal)
    rows = list(
        await database.scalars(
            select(InventoryLocation)
            .where(InventoryLocation.company_id == context.company_id)
            .order_by(InventoryLocation.active.desc(), InventoryLocation.name)
        )
    )
    return [LocationResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/locations", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    payload: LocationCreate, principal: CanManageLocations, database: DatabaseSession
) -> LocationResponse:
    context = get_request_context(principal)
    location = InventoryLocation(
        company_id=context.company_id,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        description=payload.description,
    )
    database.add(location)
    await database.commit()
    await database.refresh(location)
    return LocationResponse.model_validate(location, from_attributes=True)


@router.patch("/locations/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: UUID,
    payload: LocationUpdate,
    principal: CanManageLocations,
    database: DatabaseSession,
) -> LocationResponse:
    context = get_request_context(principal)
    location = await database.scalar(
        select(InventoryLocation).where(
            InventoryLocation.id == location_id,
            InventoryLocation.company_id == context.company_id,
        )
    )
    if location is None:
        raise HTTPException(status_code=404, detail="Local de estoque nao encontrado.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(location, field, value.strip().upper() if field == "code" and value else value)
    location.updated_at = utc_now()
    await database.commit()
    await database.refresh(location)
    return LocationResponse.model_validate(location, from_attributes=True)


@router.get("/items", response_model=list[ItemResponse])
async def list_items(
    principal: CanViewInventory,
    database: DatabaseSession,
    low_stock_only: bool = Query(default=False),
) -> list[ItemResponse]:
    context = get_request_context(principal)
    rows = list(
        await database.scalars(
            select(InventoryItem)
            .where(
                InventoryItem.company_id == context.company_id,
                InventoryItem.archived_at.is_(None),
            )
            .order_by(InventoryItem.name)
        )
    )
    responses = [await _item_response(database, row) for row in rows]
    return [item for item in responses if item.low_stock] if low_stock_only else responses


@router.post("/items", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate, principal: CanManageItems, database: DatabaseSession
) -> ItemResponse:
    context = get_request_context(principal)
    if payload.category_id is not None:
        category = await database.scalar(
            select(InventoryCategory.id).where(
                InventoryCategory.id == payload.category_id,
                InventoryCategory.company_id == context.company_id,
                InventoryCategory.active.is_(True),
            )
        )
        if category is None:
            raise HTTPException(status_code=404, detail="Categoria ativa nao encontrada.")
    item = InventoryItem(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    item.sku = item.sku.strip().upper()
    item.name = item.name.strip()
    database.add(item)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="inventory.item.created",
        target_type="inventory_item",
        target_id=item.id,
        details={"sku": item.sku, "name": item.name},
    )
    await database.commit()
    await database.refresh(item)
    return await _item_response(database, item)


@router.patch("/items/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: UUID,
    payload: ItemUpdate,
    principal: CanManageItems,
    database: DatabaseSession,
) -> ItemResponse:
    context = get_request_context(principal)
    item = await _item(database, item_id=item_id, company_id=context.company_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "sku" and value:
            value = value.strip().upper()
        if field == "name" and value:
            value = value.strip()
        setattr(item, field, value)
    item.updated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="inventory.item.updated",
        target_type="inventory_item",
        target_id=item.id,
        details={"fields": sorted(payload.model_fields_set)},
    )
    await database.commit()
    await database.refresh(item)
    return await _item_response(database, item)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_item(
    item_id: UUID, principal: CanManageItems, database: DatabaseSession
) -> Response:
    context = get_request_context(principal)
    item = await _item(database, item_id=item_id, company_id=context.company_id)
    total = Decimal(
        await database.scalar(
            select(func.coalesce(func.sum(InventoryBalance.quantity), 0)).where(
                InventoryBalance.company_id == context.company_id,
                InventoryBalance.item_id == item.id,
            )
        )
        or 0
    )
    if total > 0:
        raise HTTPException(
            status_code=409,
            detail="Zere o saldo do item antes de arquiva-lo.",
        )
    item.active = False
    item.archived_at = utc_now()
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/items/{item_id}/balances", response_model=list[BalanceResponse])
async def list_item_balances(
    item_id: UUID, principal: CanViewInventory, database: DatabaseSession
) -> list[BalanceResponse]:
    context = get_request_context(principal)
    await _item(database, item_id=item_id, company_id=context.company_id)
    rows = list(
        await database.scalars(
            select(InventoryBalance)
            .where(
                InventoryBalance.company_id == context.company_id,
                InventoryBalance.item_id == item_id,
            )
            .order_by(InventoryBalance.updated_at.desc())
        )
    )
    return [BalanceResponse.model_validate(row, from_attributes=True) for row in rows]


@router.get("/movements", response_model=list[MovementResponse])
async def list_movements(
    principal: CanViewInventory,
    database: DatabaseSession,
    item_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
) -> list[MovementResponse]:
    context = get_request_context(principal)
    statement = select(InventoryMovement).where(InventoryMovement.company_id == context.company_id)
    if item_id is not None:
        statement = statement.where(InventoryMovement.item_id == item_id)
    rows = list(
        await database.scalars(
            statement.order_by(InventoryMovement.occurred_at.desc()).limit(limit)
        )
    )
    return [MovementResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/movements", response_model=MovementResponse, status_code=status.HTTP_201_CREATED)
async def create_movement(
    payload: MovementCreate, principal: CanCreateMovements, database: DatabaseSession
) -> MovementResponse:
    context = get_request_context(principal)
    item = await _item(database, item_id=payload.item_id, company_id=context.company_id)
    if not item.active:
        raise HTTPException(status_code=409, detail="O item esta inativo.")
    await _location(database, location_id=payload.location_id, company_id=context.company_id)
    balance = await database.scalar(
        select(InventoryBalance)
        .where(
            InventoryBalance.company_id == context.company_id,
            InventoryBalance.item_id == payload.item_id,
            InventoryBalance.location_id == payload.location_id,
        )
        .with_for_update()
    )
    if balance is None:
        balance = InventoryBalance(
            company_id=context.company_id,
            item_id=payload.item_id,
            location_id=payload.location_id,
            quantity=Decimal("0"),
        )
        database.add(balance)
        await database.flush()
    previous = balance.quantity
    if payload.movement_type == "adjustment":
        resulting = payload.adjusted_quantity or Decimal("0")
        movement_quantity = abs(resulting - previous)
        if movement_quantity == 0:
            raise HTTPException(status_code=409, detail="O saldo informado ja e o saldo atual.")
    else:
        movement_quantity = payload.quantity or Decimal("0")
        resulting = (
            previous + movement_quantity
            if payload.movement_type == "in"
            else previous - movement_quantity
        )
    if resulting < 0:
        raise HTTPException(status_code=409, detail="Saldo insuficiente para esta saida.")
    balance.quantity = resulting
    balance.updated_at = utc_now()
    movement = InventoryMovement(
        company_id=context.company_id,
        item_id=payload.item_id,
        location_id=payload.location_id,
        created_by_user_id=context.user_id,
        movement_type=payload.movement_type,
        quantity=movement_quantity,
        previous_quantity=previous,
        resulting_quantity=resulting,
        reason=payload.reason.strip(),
        reference=payload.reference,
    )
    database.add(movement)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action=f"inventory.movement.{payload.movement_type}",
        target_type="inventory_movement",
        target_id=movement.id,
        details={
            "item_id": str(payload.item_id),
            "location_id": str(payload.location_id),
            "previous": str(previous),
            "resulting": str(resulting),
        },
    )
    await database.commit()
    await database.refresh(movement)
    return MovementResponse.model_validate(movement, from_attributes=True)
