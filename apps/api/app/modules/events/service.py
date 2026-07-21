from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution_context import ExecutionContext, bind_execution_context
from app.core.security import utc_now
from app.modules.events.models import OutboxEvent
from app.modules.events.repository import (
    claim_pending_events,
    mark_event_failed,
    mark_event_published,
)
from app.modules.events.schemas import DomainEventCreate, DomainEventEnvelope

DEFAULT_EVENT_STREAM = "orkestral:domain-events:v1"


class EventTransport(Protocol):
    async def publish(self, event: DomainEventEnvelope) -> str | None: ...


@dataclass(frozen=True, slots=True)
class DispatchResult:
    claimed: int
    published: int
    failed: int
    dead_lettered: int


class RedisStreamTransport:
    def __init__(
        self,
        redis_url: str,
        *,
        stream_name: str = DEFAULT_EVENT_STREAM,
        max_length: int = 100_000,
    ) -> None:
        self._redis = Redis.from_url(redis_url, decode_responses=True)
        self._stream_name = stream_name
        self._max_length = max_length

    async def publish(self, event: DomainEventEnvelope) -> str | None:
        serialized = json.dumps(event.model_dump(mode="json"), separators=(",", ":"))
        stream_id = await self._redis.xadd(
            self._stream_name,
            {"event": serialized},
            maxlen=self._max_length,
            approximate=True,
        )
        return str(stream_id) if stream_id is not None else None

    async def close(self) -> None:
        await self._redis.aclose()


def event_envelope(event: OutboxEvent) -> DomainEventEnvelope:
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


def enqueue_domain_event(database: AsyncSession, event: DomainEventCreate) -> OutboxEvent:
    now = utc_now()
    row = OutboxEvent(
        id=uuid4(),
        company_id=event.company_id,
        actor_user_id=event.actor_user_id,
        event_type=event.event_type,
        event_version=event.event_version,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
        classification=event.classification,
        payload=event.payload,
        status="pending",
        attempt_count=0,
        max_attempts=8,
        available_at=now,
        created_at=now,
        updated_at=now,
    )
    database.add(row)
    return row


async def dispatch_outbox_batch(
    database: AsyncSession,
    transport: EventTransport,
    *,
    worker_id: str,
    limit: int = 100,
) -> DispatchResult:
    events = await claim_pending_events(database, worker_id=worker_id, limit=limit)
    published = 0
    failed = 0
    dead_lettered = 0

    for event in events:
        try:
            context = ExecutionContext(
                company_id=event.company_id,
                actor_user_id=event.actor_user_id,
                correlation_id=event.correlation_id or event.id,
                source="outbox.dispatch",
                environment="worker",
            )
            with bind_execution_context(context):
                external_id = await transport.publish(event_envelope(event))
        except Exception as exc:
            mark_event_failed(event, type(exc).__name__)
            failed += 1
            dead_lettered += int(event.status == "dead_letter")
        else:
            mark_event_published(event, external_id)
            published += 1

    await database.commit()
    return DispatchResult(
        claimed=len(events),
        published=published,
        failed=failed,
        dead_lettered=dead_lettered,
    )
