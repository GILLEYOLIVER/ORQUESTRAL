from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.core.schemas import StrictSchema

ProjectStatus = Literal["planning", "active", "on_hold", "completed", "cancelled"]
TaskStatus = Literal["todo", "in_progress", "blocked", "done", "cancelled"]
Priority = Literal["low", "normal", "high", "urgent"]


class ProjectCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=10_000)
    status: ProjectStatus = "planning"
    priority: Priority = "normal"
    start_date: date | None = None
    due_date: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> ProjectCreate:
        self.name = self.name.strip()
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValueError("A data final deve ser igual ou posterior a data inicial.")
        return self


class ProjectUpdate(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=10_000)
    status: ProjectStatus | None = None
    priority: Priority | None = None
    start_date: date | None = None
    due_date: date | None = None


class ProjectResponse(StrictSchema):
    id: UUID
    name: str
    description: str | None
    status: ProjectStatus
    priority: Priority
    start_date: date | None
    due_date: date | None
    completed_at: datetime | None
    task_total: int
    task_done: int
    progress_percent: int
    created_at: datetime
    updated_at: datetime


class ProjectTaskCreate(StrictSchema):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    status: TaskStatus = "todo"
    priority: Priority = "normal"
    due_date: date | None = None
    position: int = Field(default=0, ge=0, le=100_000)


class ProjectTaskUpdate(StrictSchema):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    status: TaskStatus | None = None
    priority: Priority | None = None
    due_date: date | None = None
    position: int | None = Field(default=None, ge=0, le=100_000)


class ProjectTaskResponse(StrictSchema):
    id: UUID
    project_id: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: Priority
    due_date: date | None
    position: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
