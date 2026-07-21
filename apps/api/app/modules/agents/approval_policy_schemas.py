from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.schemas import StrictSchema

JsonScalar = str | int | float | bool | None


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
    def validate_amount_range(self) -> Self:
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
