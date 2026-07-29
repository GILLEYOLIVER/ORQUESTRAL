from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.core.schemas import StrictSchema


class CommentCreate(StrictSchema):
    body: str = Field(min_length=1, max_length=5000)
    parent_comment_id: UUID | None = None
    mentioned_user_ids: list[UUID] = Field(default_factory=list, max_length=30)

    @field_validator("mentioned_user_ids")
    @classmethod
    def unique_mentions(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Não repita pessoas mencionadas.")
        return value


class CommentResponse(StrictSchema):
    id: UUID
    resource_type: Literal["report", "dashboard"]
    resource_id: UUID
    parent_comment_id: UUID | None
    body: str
    created_by_user_id: UUID
    mentioned_user_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class FollowResponse(StrictSchema):
    resource_type: Literal["report", "dashboard"]
    resource_id: UUID
    following: bool
