from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

SupportChannel = Literal["web", "email", "phone", "whatsapp", "other"]
AgentAvailability = Literal["offline", "available", "busy", "away"]


def _compact(value: str) -> str:
    return " ".join(value.split())


class SupportSkillCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str | None = Field(default=None, max_length=500)

    _normalize_name = field_validator("name")(lambda value: _compact(value))
    _normalize_key = field_validator("key")(lambda value: value.strip().lower())
    _normalize_description = field_validator("description")(
        lambda value: _compact(value) if value else None
    )


class SupportSkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key: str
    description: str | None
    is_active: bool


class AgentSkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: UUID
    proficiency: int = Field(ge=1, le=5)


class SupportAgentCapacityUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AgentAvailability = "available"
    queue_id: UUID | None = None
    max_active_tickets: int = Field(default=5, ge=1, le=100)
    languages: list[str] = Field(default_factory=list, max_length=20)
    accepted_channels: list[SupportChannel] = Field(default_factory=list, max_length=5)
    skills: list[AgentSkillInput] = Field(default_factory=list, max_length=100)

    @field_validator("languages")
    @classmethod
    def normalize_languages(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            language = value.strip().lower()
            if not re.fullmatch(r"[a-z]{2}(?:-[a-z]{2})?", language):
                raise ValueError("Use idiomas no formato pt ou pt-br.")
            if language not in normalized:
                normalized.append(language)
        return normalized

    @field_validator("accepted_channels")
    @classmethod
    def unique_channels(cls, values: list[SupportChannel]) -> list[SupportChannel]:
        return list(dict.fromkeys(values))

    @field_validator("skills")
    @classmethod
    def unique_skills(cls, values: list[AgentSkillInput]) -> list[AgentSkillInput]:
        if len({item.skill_id for item in values}) != len(values):
            raise ValueError("Uma habilidade não pode ser repetida.")
        return values


class SupportQueueSkillsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_skill_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("required_skill_ids")
    @classmethod
    def unique_required_skills(cls, values: list[UUID]) -> list[UUID]:
        if len(set(values)) != len(values):
            raise ValueError("Uma habilidade não pode ser repetida.")
        return values


class SupportRoutingAgentResponse(BaseModel):
    user_id: UUID
    user_name: str
    status: AgentAvailability
    queue_id: UUID | None
    max_active_tickets: int
    active_tickets: int
    languages: list[str]
    accepted_channels: list[SupportChannel]
    skills: list[AgentSkillInput]


class SupportQueueRoutingResponse(BaseModel):
    queue_id: UUID
    queue_name: str
    required_skill_ids: list[UUID]


class SupportRoutingConfigurationResponse(BaseModel):
    skills: list[SupportSkillResponse]
    agents: list[SupportRoutingAgentResponse]
    queues: list[SupportQueueRoutingResponse]


class SupportRoutingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language_code: str | None = Field(default=None, max_length=12)
    required_skill_id: UUID | None = None

    @field_validator("language_code")
    @classmethod
    def normalize_language(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().lower()
        if not re.fullmatch(r"[a-z]{2}(?:-[a-z]{2})?", normalized):
            raise ValueError("Use o idioma no formato pt ou pt-br.")
        return normalized


class SupportRoutingAssignRequest(SupportRoutingRequest):
    candidate_user_id: UUID | None = None


class SupportRoutingCandidateResponse(BaseModel):
    user_id: UUID
    user_name: str
    score: int
    active_tickets: int
    max_active_tickets: int
    load_percent: int
    proficiency: int | None
    reasons: list[str]


class SupportRoutingRecommendationResponse(BaseModel):
    ticket_id: UUID
    channel: SupportChannel
    language_code: str | None
    required_skill_ids: list[UUID]
    candidates: list[SupportRoutingCandidateResponse]
    explanation: str


class SupportRoutingAssignmentResponse(BaseModel):
    ticket_id: UUID
    assigned_user_id: UUID
    assigned_user_name: str
    score: int
    reasons: list[str]
    assigned: Literal[True] = True
