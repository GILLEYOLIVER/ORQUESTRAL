from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.middleware import client_ip_address
from app.core.tenancy import PlatformAdmin, Principal, require_permission
from app.modules.audit.repository import AuditFilters
from app.modules.audit.schemas import (
    AuditEventPage,
    AuditEventResponse,
    PurgeAuditEventsRequest,
    PurgeAuditEventsResponse,
)
from app.modules.audit.service import AuditRetentionError, AuditService
from app.modules.companies.models import Company

router = APIRouter(prefix="/audit", tags=["audit"])
AuditViewer = Annotated[Principal, Depends(require_permission("audit.view"))]


@router.get("/events", response_model=AuditEventPage)
async def list_audit_events(
    principal: AuditViewer,
    database: DatabaseSession,
    action: str | None = Query(default=None, max_length=120),
    resource_type: str | None = Query(default=None, max_length=120),
    actor_user_id: UUID | None = None,
    created_from: datetime | None = None,
    created_until: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> AuditEventPage:
    if principal.company is None:
        raise HTTPException(status_code=409, detail="Selecione uma empresa para continuar.")
    events, total = await AuditService(database).list_events(
        company_id=principal.company.id,
        filters=AuditFilters(
            action=action,
            resource_type=resource_type,
            actor_user_id=actor_user_id,
            created_from=created_from,
            created_until=created_until,
        ),
        page=page,
        page_size=page_size,
    )
    return AuditEventPage(
        items=[AuditEventResponse.model_validate(event, from_attributes=True) for event in events],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/events/purge", response_model=PurgeAuditEventsResponse)
async def purge_audit_events(
    payload: PurgeAuditEventsRequest,
    request: Request,
    principal: PlatformAdmin,
    database: DatabaseSession,
    settings: RequestSettings,
) -> PurgeAuditEventsResponse:
    if await database.get(Company, payload.company_id) is None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    service = AuditService(database)
    try:
        purged = await service.purge(
            company_id=payload.company_id,
            actor_user_id=principal.user.id,
            before=payload.before,
            reason=payload.reason,
            retention_days=settings.audit_retention_days,
            request_id=getattr(request.state, "request_id", "unknown"),
            ip_address=client_ip_address(request),
            user_agent=request.headers.get("user-agent"),
        )
    except AuditRetentionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await database.commit()
    return PurgeAuditEventsResponse(
        purged=purged,
        retention_days=settings.audit_retention_days,
    )
