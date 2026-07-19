from fastapi import APIRouter
from pydantic import BaseModel

from app.core.dependencies import RequestSettings

router = APIRouter(prefix="/system", tags=["system"])


class VersionResponse(BaseModel):
    service: str
    version: str
    commit: str
    environment: str
    deployed_at: str | None


class CapabilitiesResponse(BaseModel):
    remote_development: bool
    n8n: bool
    object_storage: bool
    background_worker: bool
    email_delivery: bool


@router.get("/version", response_model=VersionResponse)
async def version(settings: RequestSettings) -> VersionResponse:
    return VersionResponse(
        service=settings.app_name,
        version=settings.app_version,
        commit=settings.deployed_commit,
        environment=settings.app_env,
        deployed_at=settings.deployed_at,
    )


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def capabilities(settings: RequestSettings) -> CapabilitiesResponse:
    return CapabilitiesResponse(
        remote_development=settings.remote_development_enabled,
        n8n=settings.n8n_enabled,
        object_storage=settings.object_storage_enabled,
        background_worker=settings.background_worker_enabled,
        email_delivery=settings.email_delivery_enabled,
    )
