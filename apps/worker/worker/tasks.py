# mypy: disable-error-code="untyped-decorator"
from __future__ import annotations

from typing import Literal, TypedDict

from worker.main import celery_app
from app.core import model_registry as _model_registry  # noqa: F401
from app.modules.knowledge.processing import process_document_sync
from app.modules.metrics.aggregation import aggregate_metrics_sync


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
