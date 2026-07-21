from __future__ import annotations

from collections.abc import Awaitable
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.metadata.record_schemas import (
    MetadataRecordCreate,
    MetadataRecordPage,
    MetadataRecordResponse,
    MetadataRecordUpdate,
)
from app.modules.metadata.record_service import (
    create_custom_record,
    delete_custom_record,
    get_custom_record,
    list_custom_records,
    update_custom_record,
)
from app.modules.metadata.schemas import (
    MetadataDesignResponse,
    MetadataDesignUpdate,
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
    get_design,
    get_entity,
    list_entities,
    publish_entity,
    update_design,
    update_draft,
    validate_entity,
)

router = APIRouter(prefix="/metadata", tags=["metadata"])

CanViewMetadata = Annotated[Principal, Depends(require_permission("metadata.view"))]
CanConfigureMetadata = Annotated[Principal, Depends(require_permission("metadata.configure"))]
CanPublishMetadata = Annotated[Principal, Depends(require_permission("metadata.publish"))]
CanViewMetadataRecords = Annotated[Principal, Depends(require_permission("metadata.records.view"))]
CanCreateMetadataRecords = Annotated[
    Principal, Depends(require_permission("metadata.records.create"))
]
CanUpdateMetadataRecords = Annotated[
    Principal, Depends(require_permission("metadata.records.update"))
]
CanDeleteMetadataRecords = Annotated[
    Principal, Depends(require_permission("metadata.records.delete"))
]


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


@router.get("/entities/{definition_id}/design", response_model=MetadataDesignResponse)
async def get_metadata_design(
    definition_id: UUID,
    request: Request,
    principal: CanViewMetadata,
    database: DatabaseSession,
) -> MetadataDesignResponse:
    return await _run(
        get_design(
            database,
            get_request_context(principal),
            definition_id,
            _correlation_id(request),
        )
    )


@router.put("/entities/{definition_id}/design", response_model=MetadataDesignResponse)
async def update_metadata_design(
    definition_id: UUID,
    payload: MetadataDesignUpdate,
    request: Request,
    principal: CanConfigureMetadata,
    database: DatabaseSession,
) -> MetadataDesignResponse:
    return await _run(
        update_design(
            database,
            get_request_context(principal),
            definition_id,
            payload,
            _correlation_id(request),
        )
    )


@router.get("/entities/{definition_id}/records", response_model=MetadataRecordPage)
async def list_metadata_records(
    definition_id: UUID,
    request: Request,
    principal: CanViewMetadataRecords,
    database: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MetadataRecordPage:
    return await _run(
        list_custom_records(
            database,
            get_request_context(principal),
            definition_id,
            _correlation_id(request),
            page=page,
            page_size=page_size,
        )
    )


@router.post(
    "/entities/{definition_id}/records",
    response_model=MetadataRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_metadata_record(
    definition_id: UUID,
    payload: MetadataRecordCreate,
    request: Request,
    principal: CanCreateMetadataRecords,
    database: DatabaseSession,
) -> MetadataRecordResponse:
    return await _run(
        create_custom_record(
            database,
            get_request_context(principal),
            definition_id,
            payload,
            _correlation_id(request),
        )
    )


@router.get(
    "/entities/{definition_id}/records/{record_id}",
    response_model=MetadataRecordResponse,
)
async def get_metadata_record(
    definition_id: UUID,
    record_id: UUID,
    request: Request,
    principal: CanViewMetadataRecords,
    database: DatabaseSession,
) -> MetadataRecordResponse:
    return await _run(
        get_custom_record(
            database,
            get_request_context(principal),
            definition_id,
            record_id,
            _correlation_id(request),
        )
    )


@router.put(
    "/entities/{definition_id}/records/{record_id}",
    response_model=MetadataRecordResponse,
)
async def update_metadata_record(
    definition_id: UUID,
    record_id: UUID,
    payload: MetadataRecordUpdate,
    request: Request,
    principal: CanUpdateMetadataRecords,
    database: DatabaseSession,
) -> MetadataRecordResponse:
    return await _run(
        update_custom_record(
            database,
            get_request_context(principal),
            definition_id,
            record_id,
            payload,
            _correlation_id(request),
        )
    )


@router.delete(
    "/entities/{definition_id}/records/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_metadata_record(
    definition_id: UUID,
    record_id: UUID,
    request: Request,
    principal: CanDeleteMetadataRecords,
    database: DatabaseSession,
    expected_version: Annotated[int, Query(ge=1)],
) -> Response:
    await _run(
        delete_custom_record(
            database,
            get_request_context(principal),
            definition_id,
            record_id,
            expected_version,
            _correlation_id(request),
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
