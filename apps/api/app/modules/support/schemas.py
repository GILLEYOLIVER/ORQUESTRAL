from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
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
    queue_id: UUID | None
    sla_policy_id: UUID | None
    first_response_due_at: datetime | None
    resolution_due_at: datetime | None
    first_responded_at: datetime | None
    breached_at: datetime | None
    satisfaction_score: int | None
    satisfaction_comment: str | None
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


class SupportQueueCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=120)
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]+$")
    description: str | None = Field(default=None, max_length=500)
    color: str = Field(default="#2f6f64", pattern=r"^#[0-9a-fA-F]{6}$")


class SupportQueueResponse(StrictSchema):
    id: UUID
    name: str
    key: str
    description: str | None
    color: str
    is_default: bool
    is_active: bool
    open_tickets: int
    unassigned_tickets: int
    breached_tickets: int


class SupportSLAPolicyCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    targets: dict[str, dict[str, int]]
    business_hours_only: bool = False

    @model_validator(mode="after")
    def validate_targets(self) -> SupportSLAPolicyCreate:
        priorities = {"low", "normal", "high", "urgent"}
        if set(self.targets) != priorities:
            raise ValueError("Informe metas para baixa, normal, alta e urgente.")
        for target in self.targets.values():
            if target.get("first_response", 0) <= 0 or target.get("resolution", 0) <= 0:
                raise ValueError("Os tempos de resposta e resolução devem ser positivos.")
        return self


class SupportSLAPolicyResponse(StrictSchema):
    id: UUID
    name: str
    description: str | None
    targets: dict[str, dict[str, int]]
    business_hours_only: bool
    is_default: bool
    is_active: bool


class SupportTicketOperationsUpdate(StrictSchema):
    queue_id: UUID | None = None
    sla_policy_id: UUID | None = None
    assignee_user_id: UUID | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None

    @model_validator(mode="after")
    def require_operational_change(self) -> SupportTicketOperationsUpdate:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos uma alteração operacional.")
        return self


class SupportSatisfactionCreate(StrictSchema):
    score: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2_000)


class SupportTicketEventResponse(StrictSchema):
    id: UUID
    ticket_id: UUID
    actor_user_id: UUID | None
    event_type: str
    description: str
    details: dict[str, Any]
    created_at: datetime


class SupportDashboardResponse(StrictSchema):
    open_tickets: int
    unassigned_tickets: int
    waiting_tickets: int
    breached_tickets: int
    due_soon_tickets: int
    resolved_today: int
    average_first_response_minutes: float
    satisfaction_average: float
    satisfaction_responses: int
