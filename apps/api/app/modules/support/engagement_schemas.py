from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.core.schemas import StrictSchema


class SupportResponseTemplateCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=160)
    shortcut: str = Field(
        min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]+$"
    )
    kind: Literal["macro", "quick_response"]
    category: str | None = Field(default=None, max_length=100)
    content: str = Field(min_length=2, max_length=10_000)

    @field_validator("name", "content")
    @classmethod
    def strip_required(cls, value: str) -> str:
        return value.strip()


class SupportResponseTemplateResponse(StrictSchema):
    id: UUID
    name: str
    shortcut: str
    kind: str
    category: str | None
    content: str
    is_active: bool
    usage_count: int
    created_at: datetime
    updated_at: datetime


class SupportKnowledgeCitationInput(StrictSchema):
    knowledge_base_id: UUID
    knowledge_document_id: UUID
    knowledge_chunk_id: UUID


class SupportKnowledgeCitationResponse(SupportKnowledgeCitationInput):
    document_name: str
    chunk_index: int
    excerpt: str
    score: float


class SupportKnowledgeSearchResponse(StrictSchema):
    query: str
    citations: list[SupportKnowledgeCitationResponse]


class SupportGuidedResponseCreate(StrictSchema):
    message: str = Field(min_length=1, max_length=10_000)
    template_id: UUID | None = None
    citations: list[SupportKnowledgeCitationInput] = Field(default_factory=list, max_length=10)
    is_internal: bool = False

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Informe uma resposta válida.")
        return normalized

    @field_validator("citations")
    @classmethod
    def unique_citations(
        cls, value: list[SupportKnowledgeCitationInput]
    ) -> list[SupportKnowledgeCitationInput]:
        if len({item.knowledge_chunk_id for item in value}) != len(value):
            raise ValueError("Não repita a mesma fonte.")
        return value


class SupportGuidedResponseResult(StrictSchema):
    interaction_id: UUID
    citations_recorded: int


class SupportSatisfactionSurveyCreate(StrictSchema):
    overall_score: int = Field(ge=1, le=5)
    resolution_score: int = Field(ge=1, le=5)
    effort_score: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2_000)


class SupportSatisfactionSurveyResponse(StrictSchema):
    id: UUID
    ticket_id: UUID
    overall_score: int
    resolution_score: int
    effort_score: int
    submitted_at: datetime


class SupportSatisfactionSummary(StrictSchema):
    responses: int
    overall_average: float
    resolution_average: float
    effort_average: float
    promoters: int
    detractors: int

