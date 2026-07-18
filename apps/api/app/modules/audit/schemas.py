from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.core.schemas import StrictSchema


class AuditEventResponse(StrictSchema):
    id: UUID
    company_id: UUID | None
    actor_user_id: UUID | None
    actor_type: Literal["user", "system", "service", "anonymous"]
    action: str
    resource_type: str
    resource_id: str | None
    before_data: dict[str, Any] | None
    after_data: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    request_id: str
    created_at: datetime


class AuditEventPage(StrictSchema):
    items: list[AuditEventResponse]
    page: int
    page_size: int
    total: int


class PurgeAuditEventsRequest(StrictSchema):
    company_id: UUID
    before: datetime
    reason: str = Field(min_length=10, max_length=500)


class PurgeAuditEventsResponse(StrictSchema):
    purged: int
    retention_days: int
