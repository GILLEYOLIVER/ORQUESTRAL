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
    beat_schedule={
        "aggregate-metrics-every-five-minutes": {
            "task": "orkestral.metrics.aggregate",
            "schedule": 300.0,
        },
        "process-notifications-every-minute": {
            "task": "orkestral.notifications.maintain",
            "schedule": 60.0,
        },
        "maintain-agent-delegations-every-minute": {
            "task": "orkestral.agents.maintain_delegations",
            "schedule": 60.0,
        },
        "dispatch-agent-runtime-every-minute": {
            "task": "orkestral.agents.dispatch_runtime",
            "schedule": 60.0,
        },
        "execute-agent-runtime-dispatches-every-fifteen-seconds": {
            "task": "orkestral.agents.execute_runtime_dispatches",
            "schedule": 15.0,
        },
        "maintain-agent-dispatch-review-sla-every-five-minutes": {
            "task": "orkestral.agents.maintain_dispatch_review_sla",
            "schedule": 300.0,
        },
        "purge-expired-agent-memories-every-five-minutes": {
            "task": "orkestral.agents.purge_expired_memories",
            "schedule": 300.0,
        },
        "run-agent-memory-response-exercises-every-five-minutes": {
            "task": "orkestral.agents.run_due_memory_response_exercises",
            "schedule": 300.0,
        },
        "maintain-agent-memory-reencryption-every-minute": {
            "task": "orkestral.agents.maintain_memory_reencryption",
            "schedule": 60.0,
        },
        "dispatch-domain-events-every-five-seconds": {
            "task": "orkestral.events.dispatch_outbox",
            "schedule": 5.0,
        },
        "process-domain-event-deliveries-every-five-seconds": {
            "task": "orkestral.events.process_deliveries",
            "schedule": 5.0,
        },
    },
)

from worker import event_tasks as _event_tasks  # noqa: E402, F401
