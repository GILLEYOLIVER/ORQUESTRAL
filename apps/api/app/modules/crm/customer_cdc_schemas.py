from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

CustomerChangeOperation = Literal["upserted", "merged", "deleted"]
CustomerCdcStatus = Literal["active", "paused"]


def _default_change_operations() -> list[CustomerChangeOperation]:
    return ["upserted", "merged", "deleted"]


class CustomerCdcSubscriptionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    consumer_key: str = Field(
        min_length=3,
        max_length=80,
        pattern=r"^[a-z][a-z0-9._-]*$",
    )
    operations: list[CustomerChangeOperation] = Field(
        default_factory=_default_change_operations,
        min_length=1,
        max_length=3,
    )
    batch_size: int = Field(default=50, ge=1, le=200)
    retention_days: int = Field(default=30, ge=1, le=365)

    @field_validator("operations")
    @classmethod
    def unique_operations(
        cls,
        operations: list[CustomerChangeOperation],
    ) -> list[CustomerChangeOperation]:
        return list(dict.fromkeys(operations))


class CustomerCdcSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    consumer_key: str
    status: CustomerCdcStatus
    operations: list[CustomerChangeOperation]
    batch_size: int
    retention_days: int
    last_acknowledged_sequence: int
    created_at: datetime
    updated_at: datetime


class CustomerChangeEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sequence_number: int
    profile_id: UUID | None
    operation: CustomerChangeOperation
    changed_fields: list[str]
    payload_fingerprint: str
    occurred_at: datetime


class CustomerCdcAcknowledgeRequest(BaseModel):
    through_sequence: int = Field(ge=1)


class CustomerCdcCheckpointResponse(BaseModel):
    subscription_id: UUID
    previous_sequence: int
    acknowledged_sequence: int
    acknowledged_at: datetime


class CustomerCdcSummaryResponse(BaseModel):
    latest_sequence: int
    retained_events: int
    active_subscriptions: int
    paused_subscriptions: int
    maximum_lag: int


class CustomerCdcEventPage(BaseModel):
    items: list[CustomerChangeEventResponse]
    next_sequence: int | None
    last_acknowledged_sequence: int | None = None


class CustomerCdcRetentionPreviewResponse(BaseModel):
    active_subscriptions: int
    cutoff_sequence: int
    effective_retention_days: int
    eligible_events: int
    protected_events: int
    reason: str


class CustomerCdcRetentionPurgeRequest(BaseModel):
    confirmation: Literal["PURGE_EXPIRED_CDC_EVENTS"]
    max_delete: int = Field(default=1_000, ge=1, le=5_000)


class CustomerCdcRetentionPurgeResponse(BaseModel):
    run_id: UUID
    cutoff_sequence: int
    effective_retention_days: int
    deleted_events: int
    executed_at: datetime
