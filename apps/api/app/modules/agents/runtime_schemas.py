from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from app.core.schemas import StrictSchema


class RequiredToolsMixin(StrictSchema):
    required_tool_keys: list[str] = Field(default_factory=list, max_length=20)
    tool_arguments: dict[str, dict[str, Any]] = Field(default_factory=dict, max_length=20)
    execution_mode: Literal["shadow", "live"] = "shadow"
    canary_percentage: int = Field(default=0, ge=0, le=100)

    @field_validator("required_tool_keys")
    @classmethod
    def normalize_tools(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().lower() for item in value if item.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Cada ferramenta só pode ser informada uma vez.")
        if any(len(item) > 160 for item in normalized):
            raise ValueError("Identificador de ferramenta muito longo.")
        return normalized

    @model_validator(mode="after")
    def validate_tool_arguments(self) -> Self:
        normalized = {key.strip().lower(): value for key, value in self.tool_arguments.items()}
        unknown = sorted(set(normalized) - set(self.required_tool_keys))
        if unknown:
            raise ValueError("Existem argumentos para ferramentas não selecionadas.")
        self.tool_arguments = normalized
        return self


class AgentScheduleCreate(RequiredToolsMixin):
    schedule_key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=2, max_length=160)
    objective: str = Field(min_length=5, max_length=1000)
    cadence_minutes: int = Field(ge=5, le=10_080)
    first_run_at: datetime | None = None


class AgentScheduleResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    agent_version_id: UUID
    schedule_key: str
    version: int
    status: Literal["draft", "published", "paused", "retired"]
    name: str
    objective: str
    cadence_minutes: int
    required_tool_keys: list[str]
    tool_arguments: dict[str, dict[str, Any]]
    execution_mode: Literal["shadow", "live"]
    canary_percentage: int
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    published_at: datetime | None


class AgentTriggerCreate(RequiredToolsMixin):
    trigger_key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=2, max_length=160)
    event_type: str = Field(min_length=3, max_length=160, pattern=r"^[a-z][a-z0-9_.-]+$")
    min_event_version: int = Field(default=1, ge=1, le=1000)
    max_event_version: int | None = Field(default=None, ge=1, le=1000)
    objective: str = Field(min_length=5, max_length=1000)

    @model_validator(mode="after")
    def validate_version_range(self) -> Self:
        if self.max_event_version is not None and self.max_event_version < self.min_event_version:
            raise ValueError("A versão máxima não pode ser menor que a mínima.")
        return self


class AgentTriggerResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    agent_version_id: UUID
    trigger_key: str
    version: int
    status: Literal["draft", "published", "paused", "retired"]
    name: str
    event_type: str
    min_event_version: int
    max_event_version: int | None
    objective: str
    required_tool_keys: list[str]
    tool_arguments: dict[str, dict[str, Any]]
    execution_mode: Literal["shadow", "live"]
    canary_percentage: int
    created_at: datetime
    published_at: datetime | None


class AgentCredentialCatalogResponse(StrictSchema):
    id: UUID
    plugin_id: UUID
    name: str
    status: Literal["active", "expired", "revoked"]
    expires_at: datetime | None
    usable: bool


class AgentCredentialBindingCreate(StrictSchema):
    credential_id: UUID
    enabled: bool = True


class AgentCredentialBindingResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    tool_key: str
    credential_id: UUID
    enabled: bool
    created_at: datetime
    updated_at: datetime


class AgentRuntimeDispatchResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    agent_version_id: UUID
    schedule_id: UUID | None
    trigger_id: UUID | None
    source_event_id: UUID | None
    source_type: Literal["schedule", "event", "retry"]
    retry_of_dispatch_id: UUID | None
    status: Literal[
        "ready",
        "blocked",
        "processing",
        "awaiting_approval",
        "simulated",
        "completed",
        "failed",
    ]
    reason_code: str | None
    error_code: str | None
    required_tool_keys: list[str]
    tool_arguments: dict[str, dict[str, Any]]
    execution_mode: Literal["shadow", "live"]
    canary_percentage: int
    agent_run_id: UUID | None
    attempt_count: int
    scheduled_for: datetime
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class AgentDispatchReviewCreate(StrictSchema):
    decision: Literal["close", "retry"]
    reason: str = Field(min_length=10, max_length=1000)
    idempotency_key: UUID


class AgentDispatchRetryApproval(StrictSchema):
    idempotency_key: UUID


class AgentDispatchReviewResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    interrupted_dispatch_id: UUID
    replacement_dispatch_id: UUID | None
    decision: Literal["close", "retry"]
    status: Literal["closed", "pending_approval", "approved"]
    reason: str
    requested_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentDispatchReviewSummaryResponse(StrictSchema):
    pending: int
    overdue: int
    closed: int
    approved: int
    repeat_interruptions: int
    average_decision_minutes: float | None
    oldest_pending_minutes: int | None
    retry_rate_percent: float
    sla_minutes: int
    escalation_minutes: int
    policy_version: int | None


class AgentDispatchReviewShift(StrictSchema):
    user_id: UUID
    weekdays: list[int] = Field(min_length=1, max_length=7)
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=1, le=24)

    @field_validator("weekdays")
    @classmethod
    def valid_weekdays(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value) or any(day < 0 or day > 6 for day in value):
            raise ValueError("Informe dias da semana únicos entre 0 e 6.")
        return sorted(value)

    @model_validator(mode="after")
    def valid_window(self) -> Self:
        if self.start_hour >= self.end_hour:
            raise ValueError("O início do turno deve ocorrer antes do término.")
        return self


class AgentDispatchReviewHoliday(StrictSchema):
    date: date
    name: str = Field(min_length=2, max_length=120)
    coverage_required: bool = False


class AgentDispatchReviewSLAPolicyCreate(StrictSchema):
    name: str = Field(min_length=3, max_length=160)
    sla_minutes: int = Field(ge=5, le=10_080)
    escalation_minutes: int = Field(ge=6, le=20_160)
    acknowledgement_minutes: int = Field(default=15, ge=1, le=1440)
    on_call_user_ids: list[UUID] = Field(default_factory=list, max_length=20)
    on_call_timezone: str = Field(default="UTC", min_length=1, max_length=64)
    on_call_start_hour: int = Field(default=0, ge=0, le=23)
    on_call_end_hour: int = Field(default=24, ge=1, le=24)
    on_call_weekdays: list[int] = Field(default_factory=lambda: list(range(7)), min_length=1)
    on_call_shifts: list[AgentDispatchReviewShift] = Field(default_factory=list, max_length=100)
    holiday_calendar: list[AgentDispatchReviewHoliday] = Field(default_factory=list, max_length=366)
    minimum_coverage: int = Field(default=1, ge=1, le=20)

    @field_validator("on_call_user_ids")
    @classmethod
    def unique_on_call_users(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("Cada usuário de plantão pode aparecer somente uma vez.")
        return value

    @field_validator("on_call_weekdays")
    @classmethod
    def valid_on_call_weekdays(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value) or any(day < 0 or day > 6 for day in value):
            raise ValueError("Informe dias da semana únicos entre 0 e 6.")
        return sorted(value)

    @field_validator("on_call_timezone")
    @classmethod
    def valid_on_call_timezone(cls, value: str) -> str:
        timezone = value.strip()
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Informe um fuso horário IANA válido.") from exc
        return timezone

    @field_validator("holiday_calendar")
    @classmethod
    def unique_holidays(
        cls, value: list[AgentDispatchReviewHoliday]
    ) -> list[AgentDispatchReviewHoliday]:
        dates = [item.date for item in value]
        if len(set(dates)) != len(dates):
            raise ValueError("Cada data pode aparecer somente uma vez no calendário.")
        return sorted(value, key=lambda item: item.date)

    @model_validator(mode="after")
    def validate_escalation(self) -> Self:
        if self.escalation_minutes <= self.sla_minutes:
            raise ValueError("O escalonamento deve ocorrer depois do SLA inicial.")
        if self.on_call_start_hour >= self.on_call_end_hour:
            raise ValueError("O início do plantão deve ocorrer antes do término.")
        return self


class AgentDispatchReviewSLAPolicyResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    version: int
    status: Literal["draft", "published", "retired"]
    name: str
    sla_minutes: int
    escalation_minutes: int
    acknowledgement_minutes: int
    on_call_user_ids: list[UUID]
    on_call_timezone: str
    on_call_start_hour: int
    on_call_end_hour: int
    on_call_weekdays: list[int]
    on_call_shifts: list[AgentDispatchReviewShift]
    holiday_calendar: list[AgentDispatchReviewHoliday]
    minimum_coverage: int
    created_at: datetime
    published_at: datetime | None


class AgentDispatchReviewCoverageIssueResponse(StrictSchema):
    code: str
    message: str
    weekday: int | None
    hour: int | None
    user_id: UUID | None


class AgentDispatchReviewCoverageResponse(StrictSchema):
    valid: bool
    minimum_coverage: int
    required_slots: int
    covered_slots: int
    issues: list[AgentDispatchReviewCoverageIssueResponse]


class AgentDispatchReviewAssignmentResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    review_id: UUID
    previous_assignment_id: UUID | None
    assigned_to_user_id: UUID
    assigned_by_user_id: UUID | None
    acknowledged_by_user_id: UUID | None
    source: Literal["on_call", "manual", "fallback"]
    status: Literal["pending", "acknowledged", "reassigned", "closed"]
    reason_code: str
    assigned_at: datetime
    acknowledged_at: datetime | None
    ended_at: datetime | None


class AgentDispatchReviewReassign(StrictSchema):
    assigned_to_user_id: UUID
    reason: str = Field(min_length=10, max_length=500)


class AgentDispatchReviewOnCallExceptionCreate(StrictSchema):
    user_id: UUID
    reason: str = Field(min_length=10, max_length=500)
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def valid_window(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("O fim da ausência deve ocorrer depois do início.")
        return self


class AgentDispatchReviewOnCallExceptionResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    policy_id: UUID
    user_id: UUID
    status: Literal["active", "cancelled"]
    reason: str
    starts_at: datetime
    ends_at: datetime
    created_at: datetime


class AgentDispatchReviewOnCallHandoffCreate(StrictSchema):
    from_user_id: UUID
    to_user_id: UUID
    reason: str = Field(min_length=10, max_length=500)
    starts_at: datetime
    ends_at: datetime
    idempotency_key: UUID

    @model_validator(mode="after")
    def valid_handoff(self) -> Self:
        if self.from_user_id == self.to_user_id:
            raise ValueError("Origem e substituto devem ser pessoas diferentes.")
        if self.ends_at <= self.starts_at:
            raise ValueError("O fim da passagem deve ocorrer depois do início.")
        return self


class AgentDispatchReviewOnCallHandoffResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    policy_id: UUID
    from_user_id: UUID
    to_user_id: UUID
    requested_by_user_id: UUID
    responded_by_user_id: UUID | None
    status: Literal["pending", "accepted", "rejected", "cancelled", "expired"]
    reason: str
    starts_at: datetime
    ends_at: datetime
    responded_at: datetime | None
    created_at: datetime


class AgentDispatchReviewOnCallHandoffDecision(StrictSchema):
    decision: Literal["accept", "reject"]
