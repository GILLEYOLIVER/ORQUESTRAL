# mypy: disable-error-code="untyped-decorator"
from __future__ import annotations

from typing import Literal, TypedDict

from app.core import model_registry as _model_registry  # noqa: F401
from app.modules.agents.coordination_execution import (
    maintain_delegations_sync,
    process_delegation_sync,
)
from app.modules.agents.memory_service import (
    maintain_due_agent_memory_response_exercises_sync,
    purge_expired_agent_memories_sync,
)
from app.modules.knowledge.processing import process_document_sync
from app.modules.metrics.aggregation import aggregate_metrics_sync
from app.modules.notifications.service import run_notification_maintenance_sync
from worker.main import celery_app


class DiagnosticResult(TypedDict):
    status: Literal["ok"]
    service: Literal["orkestral-worker"]


@celery_app.task(name="orkestral.diagnostic_ping")
def diagnostic_ping() -> DiagnosticResult:
    return {"status": "ok", "service": "orkestral-worker"}


@celery_app.task(name="orkestral.knowledge.process_document")
def process_knowledge_document(document_id: str) -> dict[str, str]:
    process_document_sync(document_id)
    return {"status": "ok", "document_id": document_id}


@celery_app.task(name="orkestral.metrics.aggregate")
def aggregate_metrics_task() -> dict[str, int | str]:
    rows = aggregate_metrics_sync()
    return {"status": "ok", "rows": rows}


@celery_app.task(name="orkestral.notifications.maintain")
def maintain_notifications_task() -> dict[str, int | str]:
    result = run_notification_maintenance_sync()
    return {"status": "ok", **result}


@celery_app.task(
    name="orkestral.agents.process_delegation",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def process_agent_delegation_task(delegation_id: str) -> dict[str, str | int]:
    return process_delegation_sync(delegation_id)


@celery_app.task(name="orkestral.agents.maintain_delegations")
def maintain_agent_delegations_task() -> dict[str, int | str]:
    return {"status": "ok", **maintain_delegations_sync()}


@celery_app.task(name="orkestral.agents.purge_expired_memories")
def purge_expired_agent_memories_task() -> dict[str, int | str]:
    return {"status": "ok", "deleted": purge_expired_agent_memories_sync()}


@celery_app.task(name="orkestral.agents.run_due_memory_response_exercises")
def run_due_agent_memory_response_exercises_task() -> dict[str, int | str]:
    return {"status": "ok", **maintain_due_agent_memory_response_exercises_sync()}
