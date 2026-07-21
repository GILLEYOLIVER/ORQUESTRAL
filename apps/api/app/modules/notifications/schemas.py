from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.core.schemas import StrictSchema

NotificationSeverity = Literal["info", "success", "warning", "error", "critical"]
ApprovalStatus = Literal["pending", "approved", "rejected", "cancelled", "expired"]


class NotificationResponse(StrictSchema):
    id: UUID
    event_type: str
    title: str
    message: str
    severity: NotificationSeverity
    resource_type: str | None
    resource_id: str | None
    data: dict[str, Any]
    delivery_status: dict[str, Any]
    read_at: datetime | None
    created_at: datetime


class NotificationSummaryResponse(StrictSchema):
    unread_count: int
    pending_approvals: int


class NotificationPreferenceResponse(StrictSchema):
    event_type: str
    in_app_enabled: bool
    email_enabled: bool
    whatsapp_enabled: bool
    whatsapp_recipient: str | None
    reminders_enabled: bool
    email_channel_configured: bool
    whatsapp_channel_configured: bool


class NotificationPreferenceUpdate(StrictSchema):
    event_type: str = Field(default="*", min_length=1, max_length=120)
    in_app_enabled: bool = True
    email_enabled: bool = False
    whatsapp_enabled: bool = False
    whatsapp_recipient: str | None = Field(default=None, max_length=40)
    reminders_enabled: bool = True

    @model_validator(mode="after")
    def require_whatsapp_recipient(self) -> NotificationPreferenceUpdate:
        recipient = (self.whatsapp_recipient or "").strip() or None
        self.whatsapp_recipient = recipient
        if self.whatsapp_enabled and recipient is None:
            raise ValueError("Informe o número autorizado para notificações por WhatsApp.")
        return self


class ApprovalActionResponse(StrictSchema):
    id: UUID
    actor_user_id: UUID | None
    action: str
    comment: str | None
    created_at: datetime


class ApprovalRequestResponse(StrictSchema):
    id: UUID
    source_type: Literal["workflow", "agent", "generic"]
    requested_by_user_id: UUID | None
    assigned_user_id: UUID | None
    workflow_id: UUID | None
    workflow_execution_id: UUID | None
    agent_tool_run_id: UUID | None
    title: str
    description: str
    context: dict[str, Any]
    status: ApprovalStatus
    reminder_at: datetime | None
    expires_at: datetime | None
    decided_at: datetime | None
    created_at: datetime
    actions: list[ApprovalActionResponse] = Field(default_factory=list)


class ApprovalDecision(StrictSchema):
    decision: Literal["approved", "rejected"]
    comment: str | None = Field(default=None, max_length=2_000)


class ApprovalComment(StrictSchema):
    comment: str = Field(min_length=1, max_length=2_000)


class ApprovalDelegationCreate(StrictSchema):
    delegate_user_id: UUID
    starts_at: datetime
    ends_at: datetime
    reason: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def validate_delegation(self) -> ApprovalDelegationCreate:
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("Início e fim devem incluir o fuso horário.")
        if self.ends_at <= self.starts_at:
            raise ValueError("O fim da cobertura deve ser posterior ao início.")
        if self.ends_at - self.starts_at > timedelta(days=90):
            raise ValueError("Uma cobertura pode durar no máximo 90 dias.")
        self.reason = self.reason.strip()
        return self


class ApprovalDelegationResponse(StrictSchema):
    id: UUID
    delegator_user_id: UUID
    delegate_user_id: UUID
    starts_at: datetime
    ends_at: datetime
    reason: str
    status: Literal["active", "revoked"]
    effective: bool
    created_at: datetime
    revoked_at: datetime | None


class ApprovalDelegateCandidateResponse(StrictSchema):
    user_id: UUID
    name: str
    email: str


class NotificationMaintenanceResponse(StrictSchema):
    reminders_created: int
