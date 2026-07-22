from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import utc_now
from app.modules.events.models import (
    EventConsumption,
    EventContract,
    EventDelivery,
    EventSubscription,
    OutboxEvent,
)
from app.modules.events.operations_schemas import EventContractCreate, EventSubscriptionCreate
from app.modules.events.repository import register_event_consumption
from app.modules.events.schemas import DomainEventEnvelope
from app.modules.workflows.execution import run_workflow
from app.modules.workflows.models import Workflow, WorkflowExecution


class EventOperationsError(ValueError):
    def __init__(
        self, detail: str, *, status_code: int = 422, code: str = "event_operation_invalid"
    ):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.code = code


class EventContractViolation(EventOperationsError):
    pass


def contract_checksum(schema: dict[str, object]) -> str:
    canonical = json.dumps(schema, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()


def _schema_types(rule: object) -> set[str]:
    if not isinstance(rule, dict):
        return set()
    raw = rule.get("type")
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        return set(raw)
    return set()


def validate_payload(payload: dict[str, object], schema: dict[str, object]) -> list[str]:
    errors: list[str] = []
    properties = schema.get("properties")
    required = schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        return ["Contrato invalido."]
    for name in required:
        if isinstance(name, str) and name not in payload:
            errors.append(f"Campo obrigatorio ausente: {name}.")
    if schema.get("additionalProperties", False) is False:
        for name in payload:
            if name not in properties:
                errors.append(f"Campo nao previsto no contrato: {name}.")
    python_types: dict[str, tuple[type[object], ...]] = {
        "string": (str,),
        "integer": (int,),
        "number": (int, float),
        "boolean": (bool,),
        "object": (dict,),
        "array": (list,),
        "null": (type(None),),
    }
    for name, value in payload.items():
        rule = properties.get(name)
        allowed = _schema_types(rule)
        if not allowed:
            continue
        if isinstance(value, bool) and "boolean" not in allowed:
            errors.append(f"Tipo invalido para {name}.")
            continue
        if not any(
            isinstance(value, python_types[item]) for item in allowed if item in python_types
        ):
            errors.append(f"Tipo invalido para {name}.")
            continue
        if (
            isinstance(rule, dict)
            and isinstance(rule.get("enum"), list)
            and value not in rule["enum"]
        ):
            errors.append(f"Valor nao permitido para {name}.")
    return errors


def backward_compatibility_errors(
    previous: dict[str, object], current: dict[str, object]
) -> list[str]:
    errors: list[str] = []
    old_properties = previous.get("properties", {})
    new_properties = current.get("properties", {})
    raw_old_required = previous.get("required", [])
    raw_new_required = current.get("required", [])
    old_required = (
        {item for item in raw_old_required if isinstance(item, str)}
        if isinstance(raw_old_required, list)
        else set()
    )
    new_required = (
        {item for item in raw_new_required if isinstance(item, str)}
        if isinstance(raw_new_required, list)
        else set()
    )
    if not isinstance(old_properties, dict) or not isinstance(new_properties, dict):
        return ["Schemas sem properties validas."]
    for name in old_required:
        if name not in new_required:
            errors.append(f"Campo obrigatorio removido: {name}.")
    for name in new_required - old_required:
        errors.append(f"Novo campo obrigatorio quebra consumidores anteriores: {name}.")
    for name, old_rule in old_properties.items():
        if name not in new_properties:
            errors.append(f"Campo removido: {name}.")
        elif _schema_types(old_rule) != _schema_types(new_properties[name]):
            errors.append(f"Tipo alterado: {name}.")
    return errors


async def create_contract(
    database: AsyncSession, *, company_id: UUID, user_id: UUID, payload: EventContractCreate
) -> EventContract:
    existing = await database.scalar(
        select(EventContract).where(
            EventContract.company_id == company_id,
            EventContract.event_type == payload.event_type,
            EventContract.version == payload.version,
        )
    )
    if existing is not None:
        raise EventOperationsError(
            "Ja existe um contrato para este tipo e versao.", status_code=409
        )
    contract = EventContract(
        company_id=company_id,
        created_by_user_id=user_id,
        event_type=payload.event_type,
        version=payload.version,
        classification=payload.classification,
        compatibility_mode=payload.compatibility_mode,
        payload_schema=payload.payload_schema,
        checksum=contract_checksum(payload.payload_schema),
    )
    database.add(contract)
    await database.flush()
    return contract


async def publish_contract(
    database: AsyncSession, *, company_id: UUID, contract_id: UUID, user_id: UUID
) -> EventContract:
    contract = await database.scalar(
        select(EventContract).where(
            EventContract.id == contract_id, EventContract.company_id == company_id
        )
    )
    if contract is None:
        raise EventOperationsError("Contrato de evento nao encontrado.", status_code=404)
    if contract.status == "published":
        return contract
    if contract.status != "draft":
        raise EventOperationsError(
            "Somente contratos em rascunho podem ser publicados.", status_code=409
        )
    previous = await database.scalar(
        select(EventContract)
        .where(
            EventContract.company_id == company_id,
            EventContract.event_type == contract.event_type,
            EventContract.status == "published",
            EventContract.version < contract.version,
        )
        .order_by(EventContract.version.desc())
        .limit(1)
    )
    if previous is not None and contract.compatibility_mode == "backward":
        errors = backward_compatibility_errors(previous.payload_schema, contract.payload_schema)
        if errors:
            raise EventOperationsError("Contrato incompativel: " + " ".join(errors))
    newest = await database.scalar(
        select(func.max(EventContract.version)).where(
            EventContract.company_id == company_id,
            EventContract.event_type == contract.event_type,
            EventContract.status == "published",
        )
    )
    if newest is not None and contract.version <= newest:
        raise EventOperationsError(
            "A nova versao deve ser maior que a versao publicada.", status_code=409
        )
    contract.status = "published"
    contract.published_by_user_id = user_id
    contract.published_at = utc_now()
    await database.flush()
    return contract


async def validate_event_contract(database: AsyncSession, event: OutboxEvent) -> None:
    contracts_count = await database.scalar(
        select(func.count(EventContract.id)).where(
            EventContract.company_id == event.company_id,
            EventContract.event_type == event.event_type,
            EventContract.status == "published",
        )
    )
    if not contracts_count:
        return
    contract = await database.scalar(
        select(EventContract).where(
            EventContract.company_id == event.company_id,
            EventContract.event_type == event.event_type,
            EventContract.version == event.event_version,
            EventContract.status == "published",
        )
    )
    if contract is None:
        raise EventContractViolation(
            "Nao existe contrato publicado para esta versao.", code="event_contract_missing"
        )
    errors = validate_payload(event.payload, contract.payload_schema)
    if errors:
        raise EventContractViolation(
            "Payload fora do contrato: " + " ".join(errors), code="event_contract_invalid_payload"
        )


async def create_subscription(
    database: AsyncSession, *, company_id: UUID, user_id: UUID, payload: EventSubscriptionCreate
) -> EventSubscription:
    contract_filters = [
        EventContract.company_id == company_id,
        EventContract.event_type == payload.event_type,
        EventContract.status == "published",
        EventContract.version >= payload.min_version,
    ]
    if payload.max_version is not None:
        contract_filters.append(EventContract.version <= payload.max_version)
    contract = await database.scalar(select(EventContract.id).where(*contract_filters))
    if contract is None:
        raise EventOperationsError("Publique um contrato compativel antes de assinar o evento.")
    if payload.workflow_id is not None:
        workflow = await database.scalar(
            select(Workflow).where(
                Workflow.id == payload.workflow_id,
                Workflow.company_id == company_id,
                Workflow.status == "active",
            )
        )
        if workflow is None:
            raise EventOperationsError(
                "A automacao deve existir, estar ativa e pertencer a empresa."
            )
    duplicate = await database.scalar(
        select(EventSubscription.id).where(
            EventSubscription.company_id == company_id,
            EventSubscription.consumer_name == payload.consumer_name,
            EventSubscription.event_type == payload.event_type,
        )
    )
    if duplicate is not None:
        raise EventOperationsError("Este consumidor ja assina o tipo de evento.", status_code=409)
    subscription = EventSubscription(
        company_id=company_id,
        created_by_user_id=user_id,
        **payload.model_dump(),
    )
    database.add(subscription)
    await database.flush()
    return subscription


async def materialize_deliveries(database: AsyncSession, event: OutboxEvent) -> int:
    subscriptions = list(
        await database.scalars(
            select(EventSubscription).where(
                EventSubscription.company_id == event.company_id,
                EventSubscription.event_type == event.event_type,
                EventSubscription.active.is_(True),
                EventSubscription.min_version <= event.event_version,
                or_(
                    EventSubscription.max_version.is_(None),
                    EventSubscription.max_version >= event.event_version,
                ),
            )
        )
    )
    created = 0
    for subscription in subscriptions:
        statement = (
            insert(EventDelivery)
            .values(
                id=uuid4(),
                company_id=event.company_id,
                event_id=event.id,
                subscription_id=subscription.id,
                status="pending",
                attempt_count=0,
                max_attempts=subscription.max_attempts,
                available_at=utc_now(),
                replay_count=0,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            .on_conflict_do_nothing(index_elements=["event_id", "subscription_id"])
            .returning(EventDelivery.id)
        )
        if await database.scalar(statement) is not None:
            created += 1
    return created


async def claim_deliveries(
    database: AsyncSession, *, worker_id: str, batch_size: int = 50
) -> list[UUID]:
    rows = list(
        await database.scalars(
            select(EventDelivery)
            .where(
                EventDelivery.status.in_(("pending", "failed")),
                EventDelivery.available_at <= utc_now(),
            )
            .order_by(EventDelivery.available_at, EventDelivery.created_at)
            .with_for_update(skip_locked=True)
            .limit(batch_size)
        )
    )
    for delivery in rows:
        delivery.status = "processing"
        delivery.locked_at = utc_now()
        delivery.locked_by = worker_id
        delivery.attempt_count += 1
    await database.flush()
    return [delivery.id for delivery in rows]


class EventConsumer(Protocol):
    async def handle(
        self,
        database: AsyncSession,
        envelope: DomainEventEnvelope,
        subscription: EventSubscription,
    ) -> None: ...


class EventConsumerRegistry:
    def __init__(self) -> None:
        self._consumers: dict[str, EventConsumer] = {}

    def register(self, delivery_mode: str, consumer: EventConsumer) -> None:
        self._consumers[delivery_mode] = consumer

    def resolve(self, delivery_mode: str) -> EventConsumer:
        consumer = self._consumers.get(delivery_mode)
        if consumer is None:
            raise EventOperationsError(
                "Consumidor de eventos indisponivel.", code="event_consumer_unavailable"
            )
        return consumer


class LedgerEventConsumer:
    async def handle(
        self,
        database: AsyncSession,
        envelope: DomainEventEnvelope,
        subscription: EventSubscription,
    ) -> None:
        del database, envelope, subscription


class WorkflowEventConsumer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def handle(
        self,
        database: AsyncSession,
        envelope: DomainEventEnvelope,
        subscription: EventSubscription,
    ) -> None:
        if subscription.workflow_id is None:
            raise EventOperationsError(
                "Assinatura sem automacao vinculada.", code="workflow_binding_missing"
            )
        workflow = await database.scalar(
            select(Workflow).where(
                Workflow.id == subscription.workflow_id,
                Workflow.company_id == envelope.company_id,
                Workflow.status == "active",
            )
        )
        if workflow is None:
            raise EventOperationsError(
                "Automacao vinculada indisponivel.", code="workflow_unavailable"
            )
        execution = await database.scalar(
            select(WorkflowExecution).where(
                WorkflowExecution.company_id == envelope.company_id,
                WorkflowExecution.workflow_id == workflow.id,
                WorkflowExecution.source_event_id == envelope.event_id,
            )
        )
        if execution is not None and execution.status in {"success", "waiting", "running"}:
            return
        if execution is None:
            execution = WorkflowExecution(
                company_id=envelope.company_id,
                workflow_id=workflow.id,
                requested_by_user_id=envelope.actor_user_id,
                source_event_id=envelope.event_id,
                source="domain_event",
                status="queued",
                input_summary={},
                output_summary={},
            )
            database.add(execution)
            await database.flush()
        result = await run_workflow(
            workflow,
            input_data={"event": envelope.model_dump(mode="json")},
            database=database,
            settings=self.settings,
            source="domain_event",
            requested_by_user_id=envelope.actor_user_id,
            existing_execution=execution,
        )
        if result.status == "error":
            raise EventOperationsError(
                result.error_summary or "A automacao falhou.", code="workflow_execution_failed"
            )


def _envelope(event: OutboxEvent) -> DomainEventEnvelope:
    return DomainEventEnvelope(
        event_id=event.id,
        event_type=event.event_type,
        event_version=event.event_version,
        company_id=event.company_id,
        actor_user_id=event.actor_user_id,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
        classification=event.classification,
        occurred_at=event.created_at,
        payload=event.payload,
    )


async def process_delivery_batch(
    database: AsyncSession,
    *,
    registry: EventConsumerRegistry,
    worker_id: str,
    batch_size: int = 50,
) -> dict[str, int]:
    delivery_ids = await claim_deliveries(database, worker_id=worker_id, batch_size=batch_size)
    await database.commit()
    result = {"claimed": len(delivery_ids), "succeeded": 0, "failed": 0, "dead_letter": 0}
    for delivery_id in delivery_ids:
        try:
            delivery = await database.get(EventDelivery, delivery_id)
            if delivery is None:
                continue
            event = await database.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.id == delivery.event_id,
                    OutboxEvent.company_id == delivery.company_id,
                )
            )
            subscription = await database.scalar(
                select(EventSubscription).where(
                    EventSubscription.id == delivery.subscription_id,
                    EventSubscription.company_id == delivery.company_id,
                )
            )
            if event is None or subscription is None:
                raise EventOperationsError(
                    "Entrega perdeu sua origem.", code="event_delivery_orphaned"
                )
            consumed = await database.scalar(
                select(EventConsumption.id).where(
                    EventConsumption.event_id == event.id,
                    EventConsumption.company_id == event.company_id,
                    EventConsumption.consumer_name == subscription.consumer_name,
                )
            )
            if consumed is None:
                await registry.resolve(subscription.delivery_mode).handle(
                    database, _envelope(event), subscription
                )
                await register_event_consumption(
                    database,
                    company_id=event.company_id,
                    event_id=event.id,
                    consumer_name=subscription.consumer_name,
                )
            delivery.status = "succeeded"
            delivery.processed_at = utc_now()
            delivery.locked_at = None
            delivery.locked_by = None
            delivery.last_error_code = None
            await database.commit()
            result["succeeded"] += 1
        except Exception as exc:
            await database.rollback()
            delivery = await database.get(EventDelivery, delivery_id)
            if delivery is None:
                continue
            code = getattr(exc, "code", type(exc).__name__)[:120]
            delivery.last_error_code = code
            delivery.locked_at = None
            delivery.locked_by = None
            if delivery.attempt_count >= delivery.max_attempts:
                delivery.status = "dead_letter"
                result["dead_letter"] += 1
            else:
                delivery.status = "failed"
                delivery.available_at = utc_now() + timedelta(
                    seconds=min(300, 2 ** min(delivery.attempt_count, 8))
                )
                result["failed"] += 1
            await database.commit()
    return result
