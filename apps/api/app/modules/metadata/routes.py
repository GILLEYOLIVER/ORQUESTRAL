from __future__ import annotations

from collections.abc import Awaitable
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.metadata.schemas import (
    MetadataEntityCreate,
    MetadataEntityDetail,
    MetadataEntityDraftUpdate,
    MetadataEntitySummary,
    MetadataValidationResponse,
)
from app.modules.metadata.service import (
    MetadataServiceError,
    create_draft_version,
    create_entity,
    get_entity,
    list_entities,
    publish_entity,
    update_draft,
    validate_entity,
)

router = APIRouter(prefix="/metadata", tags=["metadata"])

CanViewMetadata = Annotated[Principal, Depends(require_permission("metadata.view"))]
CanConfigureMetadata = Annotated[Principal, Depends(require_permission("metadata.configure"))]
CanPublishMetadata = Annotated[Principal, Depends(require_permission("metadata.publish"))]


async def _run[ResultT](operation: Awaitable[ResultT]) -> ResultT:
    try:
        return await operation
    except MetadataServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _correlation_id(request: Request) -> UUID:
    request_id = getattr(request.state, "request_id", None)
    try:
        return UUID(str(request_id))
    except (TypeError, ValueError):
        return uuid4()


@router.get("/entities", response_model=list[MetadataEntitySummary])
async def list_metadata_entities(
    request: Request,
    principal: CanViewMetadata,
    database: DatabaseSession,
) -> list[MetadataEntitySummary]:
    return await _run(
        list_entities(database, get_request_context(principal), _correlation_id(request))
    )


@router.post(
    "/entities",
    response_model=MetadataEntityDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_metadata_entity(
    payload: MetadataEntityCreate,
    request: Request,
    principal: CanConfigureMetadata,
    database: DatabaseSession,
) -> MetadataEntityDetail:
    return await _run(
        create_entity(
            database,
            get_request_context(principal),
            payload,
            _correlation_id(request),
        )
    )


@router.get("/entities/{definition_id}", response_model=MetadataEntityDetail)
async def get_metadata_entity(
    definition_id: UUID,
    request: Request,
    principal: CanViewMetadata,
    database: DatabaseSession,
) -> MetadataEntityDetail:
    return await _run(
        get_entity(
            database,
            get_request_context(principal),
            definition_id,
            _correlation_id(request),
        )
    )


@router.put("/entities/{definition_id}/draft", response_model=MetadataEntityDetail)
async def update_metadata_draft(
    definition_id: UUID,
    payload: MetadataEntityDraftUpdate,
    request: Request,
    principal: CanConfigureMetadata,
    database: DatabaseSession,
) -> MetadataEntityDetail:
    return await _run(
        update_draft(
            database,
            get_request_context(principal),
            definition_id,
            payload,
            _correlation_id(request),
        )
    )


@router.post(
    "/entities/{definition_id}/versions",
    response_model=MetadataEntityDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_metadata_draft_version(
    definition_id: UUID,
    request: Request,
    principal: CanConfigureMetadata,
    database: DatabaseSession,
) -> MetadataEntityDetail:
    return await _run(
        create_draft_version(
            database,
            get_request_context(principal),
            definition_id,
            _correlation_id(request),
        )
    )


@router.post(
    "/entities/{definition_id}/validate",
    response_model=MetadataValidationResponse,
)
async def validate_metadata_entity(
    definition_id: UUID,
    request: Request,
    principal: CanConfigureMetadata,
    database: DatabaseSession,
) -> MetadataValidationResponse:
    return await _run(
        validate_entity(
            database,
            get_request_context(principal),
            definition_id,
            _correlation_id(request),
        )
    )


@router.post("/entities/{definition_id}/publish", response_model=MetadataEntityDetail)
async def publish_metadata_entity(
    definition_id: UUID,
    request: Request,
    principal: CanPublishMetadata,
    database: DatabaseSession,
) -> MetadataEntityDetail:
    return await _run(
        publish_entity(
            database,
            get_request_context(principal),
            definition_id,
            _correlation_id(request),
        )
    )
