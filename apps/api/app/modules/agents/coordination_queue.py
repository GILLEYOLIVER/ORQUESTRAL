from __future__ import annotations

from uuid import UUID

from celery import Celery

from app.core.config import Settings


def enqueue_delegation(settings: Settings, delegation_id: UUID) -> None:
    if not settings.background_worker_enabled:
        return
    Celery(broker=str(settings.celery_broker_url)).send_task(
        "orkestral.agents.process_delegation", args=[str(delegation_id)]
    )
