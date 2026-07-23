from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CustomerSyncAdapterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    version: str
    name: str
    description: str
    transports: list[str]
    requires_credential: bool
    supports_scheduled_dispatch: bool


class CustomerSyncAdapterHealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    connector_id: UUID
    adapter_key: str
    adapter_version: str
    status: Literal["ready", "unverified", "degraded", "blocked"]
    error_code: str | None
    latency_ms: int
    checked_at: datetime


class CustomerSyncDispatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    connector_id: UUID
    adapter_key: str
    adapter_version: str
    schedule_slot: datetime
    status: Literal["pending", "claimed", "acknowledged", "failed", "expired"]
    attempts: int
    available_at: datetime
    error_code: str | None
    created_at: datetime
    claimed_at: datetime | None
    completed_at: datetime | None


class CustomerSyncSchedulerSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    health_ready: int
    health_unverified: int
    health_degraded: int
    health_blocked: int
    dispatch_pending: int
    dispatch_claimed: int
    dispatch_failed: int
    oldest_pending_at: datetime | None
