from __future__ import annotations

from datetime import date, datetime, time
from itertools import pairwise
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
EscalationAction = Literal["notify", "prioritize", "reassign_queue", "reassign_user"]


class SupportCalendarWindow(BaseModel):
    start: time
    end: time

    @model_validator(mode="after")
    def validate_window(self) -> SupportCalendarWindow:
        if self.start >= self.end:
            raise ValueError("O início do turno deve ser anterior ao fim.")
        return self


class SupportBusinessCalendarCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    timezone: str = Field(default="America/Sao_Paulo", max_length=80)
    weekly_schedule: dict[Weekday, list[SupportCalendarWindow]]
    holidays: list[date] = Field(default_factory=list, max_length=366)
    is_default: bool = False

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Fuso horário inválido.") from exc
        return value

    @model_validator(mode="after")
    def validate_schedule(self) -> SupportBusinessCalendarCreate:
        if not any(self.weekly_schedule.values()):
            raise ValueError("Informe ao menos um turno de atendimento.")
        for windows in self.weekly_schedule.values():
            ordered = sorted(windows, key=lambda item: item.start)
            if any(
                current.end > following.start
                for current, following in pairwise(ordered)
            ):
                raise ValueError("Turnos do mesmo dia não podem se sobrepor.")
        return self


class SupportBusinessCalendarResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    timezone: str
    weekly_schedule: dict[str, list[dict[str, str]]]
    holidays: list[str]
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SupportEscalationPolicyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    sla_policy_id: UUID
    calendar_id: UUID
    warning_minutes_before: int = Field(default=30, ge=0, le=10_080)
    action: EscalationAction = "notify"
    escalation_queue_id: UUID | None = None
    escalation_user_id: UUID | None = None

    @model_validator(mode="after")
    def validate_target(self) -> SupportEscalationPolicyCreate:
        if self.action == "reassign_queue" and self.escalation_queue_id is None:
            raise ValueError("Selecione a fila de escalonamento.")
        if self.action == "reassign_user" and self.escalation_user_id is None:
            raise ValueError("Selecione o usuário de escalonamento.")
        return self


class SupportEscalationPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    sla_policy_id: UUID
    calendar_id: UUID
    warning_minutes_before: int
    action: EscalationAction
    escalation_queue_id: UUID | None
    escalation_user_id: UUID | None
    is_active: bool
    created_at: datetime


class SupportEscalationEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_id: UUID
    policy_id: UUID
    kind: Literal["warning", "breach"]
    status: Literal["applied", "skipped"]
    action: EscalationAction
    deadline_at: datetime
    details: dict[str, object]
    occurred_at: datetime


class SupportEscalationSummary(BaseModel):
    active_policies: int
    due_soon: int
    breached: int
    warnings_sent: int
    escalations_applied: int
    calendar_open: bool


class SupportEscalationMaintenanceResponse(BaseModel):
    evaluated: int
    warnings: int
    escalations: int
    skipped_outside_calendar: int
