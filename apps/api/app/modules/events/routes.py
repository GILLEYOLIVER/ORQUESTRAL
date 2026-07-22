from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.models import EventContract, EventDelivery, EventSubscription, OutboxEvent
from app.modules.events.operations_schemas import (
    EventContractCreate,
    EventContractResponse,
    EventDeliveryResponse,
    EventOperationsSummary,
    EventReplayResponse,
    EventSubscriptionCreate,
    EventSubscriptionPatch,
    EventSubscriptionResponse,
    OutboxEventResponse,
)
from app.modules.events.operations_service import (
    EventOperationsError,
    create_contract,
    create_subscription,
    publish_contract,
)

router = APIRouter(prefix="/events", tags=["events"])
CanViewEvents = Annotated[Principal, Depends(require_permission("events.view"))]
CanConfigureEvents = Annotated[Principal, Depends(require_permission("events.configure"))]
CanReplayEvents = Annotated[Principal, Depends(require_permission("events.replay"))]


def _raise_operation(error: EventOperationsError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/summary", response_model=EventOperationsSummary)
async def operations_summary(
    principal: CanViewEvents, database: DatabaseSession
) -> EventOperationsSummary:
    company_id = get_request_context(principal).company_id
    contracts = await database.scalar(
        select(func.count(EventContract.id)).where(EventContract.company_id == company_id)
    )
    subscriptions = await database.scalar(
        select(func.count(EventSubscription.id)).where(EventSubscription.company_id == company_id)
    )
    pending = await database.scalar(
        select(func.count(EventDelivery.id)).where(
            EventDelivery.company_id == company_id,
            EventDelivery.status.in_(("pending", "processing", "failed")),
        )
    )
    dead_letters = await database.scalar(
        select(func.count(EventDelivery.id)).where(
            EventDelivery.company_id == company_id, EventDelivery.status == "dead_letter"
        )
    )
    failed_outbox = await database.scalar(
        select(func.count(OutboxEvent.id)).where(
            OutboxEvent.company_id == company_id, OutboxEvent.status.in_(("failed", "dead_letter"))
        )
    )
    return EventOperationsSummary(
        contracts=contracts or 0,
        subscriptions=subscriptions or 0,
        pending_deliveries=pending or 0,
        dead_letters=dead_letters or 0,
        failed_outbox=failed_outbox or 0,
    )


@router.get("/contracts", response_model=list[EventContractResponse])
async def list_contracts(
    principal: CanViewEvents, database: DatabaseSession
) -> list[EventContractResponse]:
    company_id = get_request_context(principal).company_id
    rows = await database.scalars(
        select(EventContract)
        .where(EventContract.company_id == company_id)
        .order_by(EventContract.event_type, EventContract.version.desc())
        .limit(250)
    )
    return [EventContractResponse.model_validate(row) for row in rows]


@router.post("/contracts", response_model=EventContractResponse, status_code=201)
async def add_contract(
    payload: EventContractCreate, principal: CanConfigureEvents, database: DatabaseSession
) -> EventContractResponse:
    context = get_request_context(principal)
    try:
        contract = await create_contract(
            database, company_id=context.company_id, user_id=context.user_id, payload=payload
        )
    except EventOperationsError as error:
        _raise_operation(error)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="event.contract.created",
        target_type="event_contract",
        target_id=contract.id,
        details={"event_type": contract.event_type, "version": contract.version},
    )
    await database.commit()
    await database.refresh(contract)
    return EventContractResponse.model_validate(contract)


@router.post("/contracts/{contract_id}/publish", response_model=EventContractResponse)
async def publish_event_contract(
    contract_id: UUID, principal: CanConfigureEvents, database: DatabaseSession
) -> EventContractResponse:
    context = get_request_context(principal)
    try:
        contract = await publish_contract(
            database,
            company_id=context.company_id,
            contract_id=contract_id,
            user_id=context.user_id,
        )
    except EventOperationsError as error:
        _raise_operation(error)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="event.contract.published",
        target_type="event_contract",
        target_id=contract.id,
        details={"event_type": contract.event_type, "version": contract.version},
    )
    await database.commit()
    await database.refresh(contract)
    return EventContractResponse.model_validate(contract)


@router.get("/subscriptions", response_model=list[EventSubscriptionResponse])
async def list_subscriptions(
    principal: CanViewEvents, database: DatabaseSession
) -> list[EventSubscriptionResponse]:
    company_id = get_request_context(principal).company_id
    rows = await database.scalars(
        select(EventSubscription)
        .where(EventSubscription.company_id == company_id)
        .order_by(EventSubscription.created_at.desc())
        .limit(250)
    )
    return [EventSubscriptionResponse.model_validate(row) for row in rows]


@router.post("/subscriptions", response_model=EventSubscriptionResponse, status_code=201)
async def add_subscription(
    payload: EventSubscriptionCreate, principal: CanConfigureEvents, database: DatabaseSession
) -> EventSubscriptionResponse:
    context = get_request_context(principal)
    try:
        subscription = await create_subscription(
            database, company_id=context.company_id, user_id=context.user_id, payload=payload
        )
    except EventOperationsError as error:
        _raise_operation(error)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="event.subscription.created",
        target_type="event_subscription",
        target_id=subscription.id,
        details={"event_type": subscription.event_type, "mode": subscription.delivery_mode},
    )
    await database.commit()
    await database.refresh(subscription)
    return EventSubscriptionResponse.model_validate(subscription)


@router.patch("/subscriptions/{subscription_id}", response_model=EventSubscriptionResponse)
async def change_subscription(
    subscription_id: UUID,
    payload: EventSubscriptionPatch,
    principal: CanConfigureEvents,
    database: DatabaseSession,
) -> EventSubscriptionResponse:
    context = get_request_context(principal)
    subscription = await database.scalar(
        select(EventSubscription).where(
            EventSubscription.id == subscription_id,
            EventSubscription.company_id == context.company_id,
        )
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="Assinatura de evento nao encontrada.")
    subscription.active = payload.active
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="event.subscription.updated",
        target_type="event_subscription",
        target_id=subscription.id,
        details={"active": payload.active},
    )
    await database.commit()
    await database.refresh(subscription)
    return EventSubscriptionResponse.model_validate(subscription)


@router.get("/deliveries", response_model=list[EventDeliveryResponse])
async def list_deliveries(
    principal: CanViewEvents,
    database: DatabaseSession,
    delivery_status: str | None = Query(default=None, alias="status", max_length=24),
) -> list[EventDeliveryResponse]:
    company_id = get_request_context(principal).company_id
    statement = select(EventDelivery).where(EventDelivery.company_id == company_id)
    if delivery_status:
        statement = statement.where(EventDelivery.status == delivery_status)
    rows = await database.scalars(statement.order_by(EventDelivery.created_at.desc()).limit(250))
    return [EventDeliveryResponse.model_validate(row) for row in rows]


@router.post("/deliveries/{delivery_id}/replay", response_model=EventReplayResponse)
async def replay_delivery(
    delivery_id: UUID, principal: CanReplayEvents, database: DatabaseSession
) -> EventReplayResponse:
    context = get_request_context(principal)
    delivery = await database.scalar(
        select(EventDelivery).where(
            EventDelivery.id == delivery_id, EventDelivery.company_id == context.company_id
        )
    )
    if delivery is None:
        raise HTTPException(status_code=404, detail="Entrega nao encontrada.")
    if delivery.status not in {"failed", "dead_letter"}:
        raise HTTPException(
            status_code=409, detail="Somente entregas falhas podem ser reprocessadas."
        )
    delivery.status = "pending"
    delivery.attempt_count = 0
    delivery.available_at = utc_now()
    delivery.locked_at = None
    delivery.locked_by = None
    delivery.last_error_code = None
    delivery.replay_count += 1
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="event.delivery.replayed",
        target_type="event_delivery",
        target_id=delivery.id,
        details={"event_id": str(delivery.event_id), "replay_count": delivery.replay_count},
    )
    await database.commit()
    return EventReplayResponse(id=delivery.id, status=delivery.status, source_id=delivery.event_id)


@router.get("/outbox", response_model=list[OutboxEventResponse])
async def list_outbox(
    principal: CanViewEvents,
    database: DatabaseSession,
    event_status: str | None = Query(default=None, alias="status", max_length=24),
) -> list[OutboxEventResponse]:
    company_id = get_request_context(principal).company_id
    statement = select(OutboxEvent).where(OutboxEvent.company_id == company_id)
    if event_status:
        statement = statement.where(OutboxEvent.status == event_status)
    rows = await database.scalars(statement.order_by(OutboxEvent.created_at.desc()).limit(250))
    return [OutboxEventResponse.model_validate(row) for row in rows]


@router.post("/outbox/{event_id}/replay", response_model=EventReplayResponse, status_code=201)
async def replay_outbox_event(
    event_id: UUID, principal: CanReplayEvents, database: DatabaseSession
) -> EventReplayResponse:
    context = get_request_context(principal)
    source = await database.scalar(
        select(OutboxEvent).where(
            OutboxEvent.id == event_id, OutboxEvent.company_id == context.company_id
        )
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Evento nao encontrado.")
    if source.status not in {"failed", "dead_letter"}:
        raise HTTPException(status_code=409, detail="Somente eventos falhos podem gerar replay.")
    replay = OutboxEvent(
        id=uuid4(),
        company_id=source.company_id,
        actor_user_id=context.user_id,
        event_type=source.event_type,
        event_version=source.event_version,
        correlation_id=source.correlation_id or source.id,
        causation_id=source.id,
        classification=source.classification,
        payload=source.payload,
        status="pending",
        attempt_count=0,
        max_attempts=source.max_attempts,
        available_at=utc_now(),
    )
    database.add(replay)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="event.outbox.replayed",
        target_type="outbox_event",
        target_id=replay.id,
        details={"source_event_id": str(source.id)},
    )
    await database.commit()
    return EventReplayResponse(id=replay.id, status=replay.status, source_id=source.id)
