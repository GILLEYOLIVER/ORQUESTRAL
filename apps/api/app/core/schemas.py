from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictSchema):
    status: Literal["ok"]
    service: str
    version: str
    request_id: str


class WorkerHealthResponse(StrictSchema):
    status: Literal["ok", "degraded"]
    component: Literal["agent-memory-worker"]
    state: Literal["idle", "healthy", "overdue"]
    monitor_secret_rotation_state: Literal["not_configured", "healthy", "due_soon"]
    monitor_secret_rotation_days_remaining: int | None
    request_id: str


class CheckResult(StrictSchema):
    status: Literal["ok", "error"]
    latency_ms: float


class ReadinessResponse(StrictSchema):
    status: Literal["ready", "not_ready"]
    checks: dict[str, CheckResult]
    request_id: str


class ProblemDetails(StrictSchema):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
    request_id: str
