from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.schemas import StrictSchema

TicketStatus = Literal["open", "in_progress", "waiting", "resolved", "closed"]
TicketPriority = Literal["low", "normal", "high", "urgent"]
TicketChannel = Literal["web", "email", "phone", "whatsapp", "other"]


def _normalized(value: str) -> str:
    return " ".join(value.strip().split())


class SupportTicketCreate(StrictSchema):
    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=10_000)
    priority: TicketPriority = "normal"
    channel: TicketChannel = "web"
    requester_contact_id: UUID | None = None
    assignee_user_id: UUID | None = None
    due_at: datetime | None = None

    @field_validator("subject")
    @classmethod
    def normalize_subject(cls, value: str) -> str:
        return _normalized(value)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return value.strip()


class SupportTicketUpdate(StrictSchema):
    subject: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=3, max_length=10_000)
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    channel: TicketChannel | None = None
    requester_contact_id: UUID | None = None
    assignee_user_id: UUID | None = None
    due_at: datetime | None = None

    @field_validator("subject")
    @classmethod
    def normalize_subject(cls, value: str | None) -> str | None:
        return _normalized(value) if value is not None else None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def require_change(self) -> SupportTicketUpdate:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos uma alteracao.")
        return self


class SupportTicketResponse(StrictSchema):
    id: UUID
    requester_contact_id: UUID | None
    assignee_user_id: UUID | None
    created_by_user_id: UUID
    subject: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    channel: TicketChannel
    due_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SupportInteractionCreate(StrictSchema):
    message: str = Field(min_length=1, max_length=5_000)
    is_internal: bool = False

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Informe uma interacao valida.")
        return normalized


class SupportInteractionResponse(StrictSchema):
    id: UUID
    ticket_id: UUID
    author_user_id: UUID
    message: str
    is_internal: bool
    created_at: datetime
