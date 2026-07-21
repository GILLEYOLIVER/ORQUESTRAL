from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utc_now
from app.modules.events.models import EventConsumption, OutboxEvent


async def claim_pending_events(
    database: AsyncSession,
    *,
    worker_id: str,
    limit: int,
    lock_timeout_seconds: int = 300,
) -> list[OutboxEvent]:
    now = utc_now()
    stale_before = now - timedelta(seconds=lock_timeout_seconds)
    statement = (
        select(OutboxEvent)
        .where(
            OutboxEvent.available_at <= now,
            OutboxEvent.attempt_count < OutboxEvent.max_attempts,
            or_(
                OutboxEvent.status.in_(("pending", "failed")),
                (OutboxEvent.status == "processing") & (OutboxEvent.locked_at < stale_before),
            ),
        )
        .order_by(OutboxEvent.created_at, OutboxEvent.id)
        .with_for_update(skip_locked=True)
        .limit(limit)
    )
    rows = list(await database.scalars(statement))
    for row in rows:
        row.status = "processing"
        row.attempt_count += 1
        row.locked_at = now
        row.locked_by = worker_id
        row.updated_at = now
    await database.flush()
    return rows


def mark_event_published(event: OutboxEvent, external_id: str | None) -> None:
    now = utc_now()
    event.status = "published"
    event.external_id = external_id
    event.published_at = now
    event.locked_at = None
    event.locked_by = None
    event.last_error_code = None
    event.updated_at = now


def mark_event_failed(event: OutboxEvent, error_code: str) -> None:
    now = utc_now()
    event.status = "dead_letter" if event.attempt_count >= event.max_attempts else "failed"
    event.last_error_code = error_code[:120]
    event.available_at = now + timedelta(seconds=min(2**event.attempt_count, 300))
    event.locked_at = None
    event.locked_by = None
    event.updated_at = now


async def register_event_consumption(
    database: AsyncSession,
    *,
    event_id: UUID,
    company_id: UUID,
    consumer_name: str,
) -> bool:
    statement = (
        insert(EventConsumption)
        .values(
            id=uuid4(),
            event_id=event_id,
            company_id=company_id,
            consumer_name=consumer_name,
            processed_at=utc_now(),
        )
        .on_conflict_do_nothing(
            index_elements=(EventConsumption.event_id, EventConsumption.consumer_name)
        )
        .returning(EventConsumption.id)
    )
    return await database.scalar(statement) is not None
