from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.core.schemas import StrictSchema


class SupportAgentAssistCreate(StrictSchema):
    agent_id: UUID


class SupportAgentAssistResponse(StrictSchema):
    id: UUID
    ticket_id: UUID
    agent_id: UUID
    agent_version_id: UUID
    status: str
    recommendation: str
    reason_code: str
    context_refs: list[dict[str, str]]
    citation_count: int
    created_at: datetime
    completed_at: datetime | None


class SupportHumanHandoffCreate(StrictSchema):
    target_user_id: UUID
    reason_code: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9_.-]+$")


class SupportHumanHandoffDecision(StrictSchema):
    decision: Literal["accepted", "rejected"]


class SupportHumanHandoffResponse(StrictSchema):
    id: UUID
    assist_run_id: UUID
    ticket_id: UUID
    target_user_id: UUID
    status: str
    reason_code: str
    created_at: datetime
    decided_at: datetime | None

