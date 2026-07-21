from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.tenancy import RequestContext

PolicyAction = Literal[
    "view",
    "list",
    "create",
    "update",
    "delete",
    "execute",
    "approve",
    "publish",
    "export",
]
RiskLevel = Literal["low", "medium", "high", "critical"]
PolicyOutcome = Literal["allow", "deny", "require_approval"]


class PolicySubject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: UUID | None = None
    company_id: UUID
    permissions: frozenset[str] = Field(default_factory=frozenset)
    is_owner: bool = False
    is_platform_admin: bool = False

    @classmethod
    def from_request_context(cls, context: RequestContext) -> PolicySubject:
        return cls(
            user_id=context.user_id,
            company_id=context.company_id,
            permissions=context.permissions,
            is_owner=context.is_owner,
            is_platform_admin=context.is_platform_admin,
        )


class PolicyResource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: UUID
    resource_type: str = Field(min_length=2, max_length=120)
    resource_id: str | None = Field(default=None, max_length=160)
    owner_user_id: UUID | None = None
    field_permissions: dict[str, frozenset[str]] = Field(default_factory=dict)


class PolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: PolicySubject
    resource: PolicyResource
    action: PolicyAction
    required_permission: str | None = Field(default=None, max_length=160)
    requested_fields: tuple[str, ...] = ()
    risk_level: RiskLevel = "low"
    allow_platform_scope: bool = False
    correlation_id: UUID


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: PolicyOutcome
    allowed: bool
    requires_approval: bool
    reason_code: str
    allowed_fields: tuple[str, ...] = ()
    denied_fields: tuple[str, ...] = ()
    policy_version: str
