from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerQualityRuleSetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=120)
    rules: dict[str, Any] = Field(
        default_factory=lambda: {
            "required": ["external_id", "display_name"],
            "email_format": True,
            "phone_min_digits": 8,
            "minimum_score": 60,
        }
    )


class CustomerQualityRuleSetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    version: int
    name: str
    status: Literal["draft", "published", "retired"]
    rules: dict[str, Any]
    created_at: datetime
    published_at: datetime | None


class CustomerIngestionRecordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_record_id: str = Field(min_length=1, max_length=160)
    external_id: str | None = Field(default=None, max_length=240)
    display_name: str | None = Field(default=None, max_length=240)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)


class CustomerIngestionJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_code: str = Field(pattern=r"^[a-z][a-z0-9._-]{1,79}$")
    source_name: str = Field(min_length=2, max_length=120)
    mode: Literal["batch", "incremental"] = "batch"
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9._:-]{8,160}$")
    cursor: str | None = Field(default=None, max_length=500)
    records: list[CustomerIngestionRecordInput] = Field(min_length=1, max_length=100)


class CustomerIngestionRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    source_record_id: str
    payload_fingerprint: str
    status: Literal["accepted", "rejected", "dead_letter"]
    error_code: str | None
    errors: list[str]
    profile_id: UUID | None
    attempts: int
    processed_at: datetime | None


class CustomerIngestionJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    source_code: str
    source_name: str
    quality_rule_version: int
    mode: Literal["batch", "incremental"]
    status: Literal["completed", "partial", "failed"]
    idempotency_key: str
    cursor: str | None
    total_records: int
    accepted_records: int
    rejected_records: int
    created_at: datetime
    completed_at: datetime | None
    records: list[CustomerIngestionRecordResponse] = Field(default_factory=list)


class CustomerDeadLetterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    job_id: UUID
    source_code: str
    source_record_id: str
    payload_fingerprint: str
    error_code: str
    errors: list[str]
    attempts: int
    created_at: datetime
    processed_at: datetime | None


class CustomerIngestionReprocess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record: CustomerIngestionRecordInput
    reason: str = Field(min_length=3, max_length=500)
