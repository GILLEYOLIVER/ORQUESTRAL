from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.schemas import HealthResponse, ReadinessResponse
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
