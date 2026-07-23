from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CustomerPrivacyRequestType = Literal["anonymization", "deletion"]
CustomerPrivacyRequestStatus = Literal[
    "received",
    "identity_verified",
    "approved",
    "rejected",
    "completed",
]
CustomerPrivacyScope = Literal[
    "profile",
    "identities",
    "consents",
    "lineage",
    "crm",
    "support",
    "marketing",
]
CustomerPrivacyDecision = Literal["approved", "rejected"]
CustomerPrivacyReasonCode = Literal[
    "data_subject_request",
    "contract_ended",
    "duplicate_record",
    "legal_obligation",
]
CustomerPrivacyHoldReason = Literal[
    "contractual",
    "regulatory",
    "litigation",
    "fraud_prevention",
]


def _default_privacy_scope() -> list[CustomerPrivacyScope]:
    return [
        "profile",
        "identities",
        "consents",
        "lineage",
        "crm",
        "support",
        "marketing",
    ]


class CustomerPrivacyRequestCreate(BaseModel):
    profile_id: UUID
    request_type: CustomerPrivacyRequestType
    request_reference: str = Field(min_length=8, max_length=200)
    reason_code: CustomerPrivacyReasonCode = "data_subject_request"
    scope: list[CustomerPrivacyScope] = Field(
        default_factory=_default_privacy_scope,
        min_length=1,
        max_length=7,
    )
    due_days: int = Field(default=15, ge=1, le=60)

    @field_validator("scope")
    @classmethod
    def unique_scope(
        cls,
        scope: list[CustomerPrivacyScope],
    ) -> list[CustomerPrivacyScope]:
        return list(dict.fromkeys(scope))


class CustomerPrivacyDecisionRequest(BaseModel):
    decision: CustomerPrivacyDecision
    reason_code: CustomerPrivacyReasonCode


class CustomerPrivacyLegalHoldRequest(BaseModel):
    enabled: bool
    reason: CustomerPrivacyHoldReason | None = None

    @model_validator(mode="after")
    def hold_requires_reason(self) -> CustomerPrivacyLegalHoldRequest:
        if self.enabled and self.reason is None:
            raise ValueError("Informe o motivo da retencao legal.")
        return self


class CustomerPrivacyRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID | None
    request_type: CustomerPrivacyRequestType
    status: CustomerPrivacyRequestStatus
    reason_code: CustomerPrivacyReasonCode
    scope: list[CustomerPrivacyScope]
    legal_hold: bool
    legal_hold_reason: CustomerPrivacyHoldReason | None
    due_at: datetime
    requested_at: datetime
    verified_at: datetime | None
    decided_at: datetime | None
    completed_at: datetime | None
    result_counts: dict[str, int]


class CustomerPrivacySummaryResponse(BaseModel):
    received: int
    awaiting_decision: int
    approved: int
    blocked_by_legal_hold: int
    completed: int
    overdue: int
