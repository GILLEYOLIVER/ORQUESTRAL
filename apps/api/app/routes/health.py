from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.schemas import HealthResponse, ReadinessResponse, WorkerHealthResponse
from app.core.security import utc_now
from app.modules.agents.memory_models import AgentMemoryExerciseSchedule
from app.services.readiness import ReadinessService

router = APIRouter(tags=["system"])


def get_readiness_service(request: Request) -> ReadinessService:
    return ReadinessService(request.app.state.resources, request.app.state.settings)


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        request_id=request.state.request_id,
    )


@router.get(
    "/health/agent-memory-scheduler",
    response_model=WorkerHealthResponse,
    responses={503: {"model": WorkerHealthResponse}},
)
async def agent_memory_scheduler_health(
    request: Request,
) -> WorkerHealthResponse | JSONResponse:
    async with request.app.state.resources.sessions() as database:
        schedules = list(
            (
                await database.execute(
                    select(
                        AgentMemoryExerciseSchedule.last_worker_heartbeat_at,
                        AgentMemoryExerciseSchedule.next_run_at,
                        AgentMemoryExerciseSchedule.heartbeat_slo_minutes,
                    )
                    .where(AgentMemoryExerciseSchedule.enabled.is_(True))
                    .limit(10_000)
                )
            ).all()
        )
    now = utc_now()
    overdue = any(
        (
            last_heartbeat is not None
            and now - last_heartbeat > timedelta(minutes=heartbeat_slo_minutes)
        )
        or (
            last_heartbeat is None
            and next_run_at is not None
            and now > next_run_at + timedelta(minutes=heartbeat_slo_minutes)
        )
        for last_heartbeat, next_run_at, heartbeat_slo_minutes in schedules
    )
    payload = WorkerHealthResponse(
        status="degraded" if overdue else "ok",
        component="agent-memory-worker",
        state="overdue" if overdue else ("healthy" if schedules else "idle"),
        request_id=request.state.request_id,
    )
    if overdue:
        return JSONResponse(
            status_code=503,
            content=payload.model_dump(mode="json"),
            headers={"Cache-Control": "no-store"},
        )
    return payload


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
async def ready(
    request: Request,
    service: Annotated[ReadinessService, Depends(get_readiness_service)],
) -> ReadinessResponse | JSONResponse:
    report = await service.run()
    payload = ReadinessResponse(
        status="ready" if report.ready else "not_ready",
        checks=report.checks,
        request_id=request.state.request_id,
    )
    if report.ready:
        return payload
    return JSONResponse(status_code=503, content=payload.model_dump())
