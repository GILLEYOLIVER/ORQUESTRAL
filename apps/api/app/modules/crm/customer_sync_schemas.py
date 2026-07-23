from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.crm.customer_ingestion_schemas import CustomerIngestionRecordInput


class CustomerSyncConnectorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_code: str = Field(pattern=r"^[a-z][a-z0-9._-]{1,79}$")
    source_name: str = Field(min_length=2, max_length=120)
    transport: Literal["push", "pull", "webhook"] = "push"
    credential_binding_id: UUID | None = None
    schedule_minutes: int = Field(default=60, ge=5, le=10_080)
    max_attempts: int = Field(default=5, ge=1, le=10)
    base_backoff_seconds: int = Field(default=30, ge=5, le=3_600)
    lease_ttl_seconds: int = Field(default=300, ge=30, le=3_600)


class CustomerSyncConnectorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    source_code: str
    source_name: str
    transport: Literal["push", "pull", "webhook"]
    status: Literal["active", "paused"]
    credential_configured: bool
    schedule_minutes: int
    max_attempts: int
    base_backoff_seconds: int
    lease_ttl_seconds: int
    has_cursor: bool
    cursor_fingerprint: str | None
    next_run_at: datetime | None
    leased_until: datetime | None
    consecutive_failures: int
    created_at: datetime
    updated_at: datetime


class CustomerSyncExecutionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9._:-]{8,160}$")
    trigger: Literal["manual", "scheduled", "webhook", "retry"] = "manual"
    cursor_after: str | None = Field(default=None, max_length=500)
    records: list[CustomerIngestionRecordInput] = Field(min_length=1, max_length=100)


class CustomerSyncRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    connector_id: UUID
    ingestion_job_id: UUID | None
    idempotency_key: str
    trigger: Literal["manual", "scheduled", "webhook", "retry"]
    status: Literal["running", "completed", "partial", "failed"]
    attempt: int
    cursor_before_fingerprint: str | None
    cursor_after_fingerprint: str | None
    total_records: int
    accepted_records: int
    rejected_records: int
    duration_ms: int | None
    error_code: str | None
    retry_at: datetime | None
    started_at: datetime
    completed_at: datetime | None


class CustomerSyncObservabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connectors_total: int
    connectors_active: int
    connectors_due: int
    connectors_leased: int
    runs_total: int
    runs_failed: int
    records_processed: int
    records_rejected: int
    success_rate: float
    average_duration_ms: int
