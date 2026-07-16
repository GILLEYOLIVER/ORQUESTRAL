# mypy: disable-error-code="untyped-decorator"
from __future__ import annotations

from typing import Literal, TypedDict

from worker.main import celery_app


class DiagnosticResult(TypedDict):
    status: Literal["ok"]
    service: Literal["orkestral-worker"]


@celery_app.task(name="orkestral.diagnostic_ping")
def diagnostic_ping() -> DiagnosticResult:
    return {"status": "ok", "service": "orkestral-worker"}
