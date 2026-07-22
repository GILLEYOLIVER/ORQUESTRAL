from __future__ import annotations

import asyncio
import socket

from app.core.config import get_settings
from app.core.resources import create_resources
from app.modules.events.operations_service import (
    EventConsumerRegistry,
    LedgerEventConsumer,
    WorkflowEventConsumer,
    process_delivery_batch,
)
from app.modules.events.service import RedisStreamTransport, dispatch_outbox_batch
from worker.main import celery_app


async def _dispatch(limit: int) -> dict[str, int]:
    settings = get_settings()
    resources = create_resources(settings)
    transport = RedisStreamTransport(str(settings.redis_url))
    try:
        async with resources.sessions() as database:
            result = await dispatch_outbox_batch(
                database,
                transport,
                worker_id=f"{socket.gethostname()}:{id(asyncio.current_task())}",
                limit=limit,
            )
            return {
                "claimed": result.claimed,
                "published": result.published,
                "failed": result.failed,
                "dead_lettered": result.dead_lettered,
            }
    finally:
        await transport.close()
        await resources.close()


@celery_app.task(  # type: ignore[untyped-decorator]
    name="orkestral.events.dispatch_outbox",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def dispatch_outbox(limit: int = 100) -> dict[str, int]:
    """Publish a bounded outbox batch to the internal Redis stream."""
    safe_limit = max(1, min(limit, 500))
    return asyncio.run(_dispatch(safe_limit))


async def _process_deliveries(limit: int) -> dict[str, int]:
    settings = get_settings()
    resources = create_resources(settings)
    registry = EventConsumerRegistry()
    registry.register("ledger", LedgerEventConsumer())
    registry.register("workflow", WorkflowEventConsumer(settings))
    try:
        async with resources.sessions() as database:
            return await process_delivery_batch(
                database,
                registry=registry,
                worker_id=f"{socket.gethostname()}:{id(asyncio.current_task())}",
                batch_size=limit,
            )
    finally:
        await resources.close()


@celery_app.task(  # type: ignore[untyped-decorator]
    name="orkestral.events.process_deliveries",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def process_event_deliveries(limit: int = 100) -> dict[str, int]:
    """Consume a bounded batch with idempotency, retry and dead-letter state."""
    return asyncio.run(_process_deliveries(max(1, min(limit, 500))))
