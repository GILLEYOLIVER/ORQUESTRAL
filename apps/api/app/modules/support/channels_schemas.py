from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

SupportChannel = Literal["email", "chat", "whatsapp", "form", "portal"]
SupportChannelStatus = Literal["active", "paused", "revoked"]
SupportPriority = Literal["low", "normal", "high", "urgent"]


class SupportChannelEndpointCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    channel: SupportChannel
    default_queue_id: UUID | None = None
    default_priority: SupportPriority = "normal"
    consent_required: bool = False

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())


class SupportChannelEndpointUpdate(BaseModel):
    status: SupportChannelStatus | None = None
    default_queue_id: UUID | None = None
    default_priority: SupportPriority | None = None
    consent_required: bool | None = None


class SupportChannelEndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    channel: SupportChannel
    status: SupportChannelStatus
    default_queue_id: UUID | None
    default_priority: SupportPriority
    consent_required: bool
    secret_fingerprint: str
    webhook_path: str
    last_received_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SupportChannelSecretResponse(SupportChannelEndpointResponse):
    webhook_secret: str = Field(min_length=32)


class SupportChannelIngressRequest(BaseModel):
    subject: str = Field(min_length=2, max_length=240)
    message: str = Field(min_length=1, max_length=20_000)
    sender_reference: str | None = Field(default=None, max_length=320)
    language_code: str | None = Field(default=None, min_length=2, max_length=16)
    consent_granted: bool | None = None

    @field_validator("subject", "message")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("O conteúdo não pode ficar vazio.")
        return normalized

    @field_validator("language_code")
    @classmethod
    def normalize_language(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else None


class SupportChannelIngressResponse(BaseModel):
    accepted: bool = True
    duplicate: bool = False
    event_id: UUID
    ticket_id: UUID | None


class SupportChannelIngressEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    endpoint_id: UUID
    ticket_id: UUID | None
    external_event_id: str
    payload_hash: str
    status: Literal["ticket_created", "rejected"]
    received_at: datetime
