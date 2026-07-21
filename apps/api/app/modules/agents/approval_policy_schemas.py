from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.schemas import StrictSchema

JsonScalar = str | int | float | bool | None


class AgentApprovalPolicyStageCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=160)
    quorum: int = Field(default=1, ge=1, le=20)
    approver_user_ids: list[UUID] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_stage(self) -> Self:
        if len(set(self.approver_user_ids)) != len(self.approver_user_ids):
            raise ValueError("Um aprovador não pode aparecer duas vezes na mesma etapa.")
        if self.quorum > len(self.approver_user_ids):
            raise ValueError("O quórum não pode ser maior que o número de aprovadores.")
        return self


class AgentApprovalPolicyStageResponse(StrictSchema):
    id: UUID
    stage_order: int
    name: str
    quorum: int
    approver_user_ids: list[UUID]


class AgentApprovalPolicyCreate(StrictSchema):
    policy_key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=2, max_length=160)
    effect: Literal["allow", "require_approval", "deny"]
    priority: int = Field(default=100, ge=0, le=1000)
    tool_key: str | None = Field(default=None, min_length=2, max_length=160)
    amount_field: str | None = Field(
        default=None, min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_.-]+$"
    )
    min_amount_microunits: int | None = Field(default=None, ge=0, le=2_000_000_000)
    max_amount_microunits: int | None = Field(default=None, ge=0, le=2_000_000_000)
    currency: str | None = Field(default=None, pattern=r"^[A-Za-z]{3}$")
    context_conditions: dict[str, JsonScalar] = Field(default_factory=dict, max_length=20)
    approval_ttl_minutes: int = Field(default=30, ge=5, le=10_080)
    assigned_user_id: UUID | None = None
    escalation_user_id: UUID | None = None
    escalation_after_minutes: int | None = Field(default=None, ge=5, le=10_079)
    approval_stages: list[AgentApprovalPolicyStageCreate] = Field(
        default_factory=list, max_length=10
    )

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else None

    @field_validator("context_conditions")
    @classmethod
    def validate_context_paths(cls, value: dict[str, JsonScalar]) -> dict[str, JsonScalar]:
        if any(not path or len(path) > 160 for path in value):
            raise ValueError("Caminho de contexto inválido.")
        return value

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if (
            self.min_amount_microunits is not None or self.max_amount_microunits is not None
        ) and not self.amount_field:
            raise ValueError("Informe amount_field para utilizar limites de valor.")
        if (
            self.min_amount_microunits is not None
            and self.max_amount_microunits is not None
            and self.max_amount_microunits < self.min_amount_microunits
        ):
            raise ValueError("O valor máximo não pode ser menor que o mínimo.")
        if self.effect != "require_approval" and any(
            value is not None
            for value in (
                self.assigned_user_id,
                self.escalation_user_id,
                self.escalation_after_minutes,
            )
        ):
            raise ValueError(
                "Aprovadores só podem ser definidos quando a política exige aprovação."
            )
        if (self.escalation_user_id is None) != (self.escalation_after_minutes is None):
            raise ValueError("Informe o aprovador substituto e o prazo de escalonamento.")
        if self.escalation_user_id is not None and self.assigned_user_id is None:
            raise ValueError("Defina o aprovador principal antes do substituto.")
        if self.escalation_user_id == self.assigned_user_id and self.escalation_user_id is not None:
            raise ValueError("O aprovador substituto deve ser diferente do principal.")
        if (
            self.escalation_after_minutes is not None
            and self.escalation_after_minutes >= self.approval_ttl_minutes
        ):
            raise ValueError("O escalonamento deve ocorrer antes da expiração da aprovação.")
        if self.approval_stages and self.effect != "require_approval":
            raise ValueError("Etapas só podem ser usadas em políticas que exigem aprovação.")
        if self.approval_stages and any(
            value is not None
            for value in (
                self.assigned_user_id,
                self.escalation_user_id,
                self.escalation_after_minutes,
            )
        ):
            raise ValueError("Use uma cadeia de etapas ou a aprovação simples, nunca as duas.")
        stage_users = [
            user_id for stage in self.approval_stages for user_id in stage.approver_user_ids
        ]
        if len(set(stage_users)) != len(stage_users):
            raise ValueError("Cada pessoa só pode participar de uma etapa da cadeia.")
        return self


class AgentApprovalPolicyResponse(StrictSchema):
    id: UUID
    agent_id: UUID
    policy_key: str
    version: int
    name: str
    status: Literal["draft", "published", "retired"]
    effect: Literal["allow", "require_approval", "deny"]
    priority: int
    tool_key: str | None
    amount_field: str | None
    min_amount_microunits: int | None
    max_amount_microunits: int | None
    currency: str | None
    context_conditions: dict[str, JsonScalar]
    approval_ttl_minutes: int
    assigned_user_id: UUID | None
    escalation_user_id: UUID | None
    escalation_after_minutes: int | None
    approval_stages: list[AgentApprovalPolicyStageResponse] = Field(default_factory=list)
    created_at: datetime
    published_at: datetime | None


class AgentApprovalPolicyEvaluationRequest(StrictSchema):
    tool_key: str = Field(min_length=2, max_length=160)
    arguments: dict[str, object] = Field(default_factory=dict)


class AgentApprovalPolicyEvaluationResponse(StrictSchema):
    allowed: bool
    requires_approval: bool
    policy_version_id: UUID | None
    policy_key: str | None
    reason: str
    approval_ttl_minutes: int
    assigned_user_id: UUID | None
    escalation_user_id: UUID | None
    escalation_after_minutes: int | None
