# mypy: disable-error-code="import-untyped"
from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "orkestral",
    broker=str(settings.celery_broker_url),
    backend=str(settings.celery_result_backend),
    include=["worker.tasks"],
)
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_track_started=True,
)
