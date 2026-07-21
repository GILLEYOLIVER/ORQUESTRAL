from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.core.schemas import StrictSchema

ProjectStatus = Literal["planning", "active", "on_hold", "completed", "cancelled"]
TaskStatus = Literal["todo", "in_progress", "blocked", "done", "cancelled"]
Priority = Literal["low", "normal", "high", "urgent"]
ProjectHealth = Literal["unknown", "on_track", "at_risk", "off_track"]
MilestoneStatus = Literal["pending", "at_risk", "completed", "cancelled"]
RiskStatus = Literal["open", "mitigating", "accepted", "closed"]


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
    portfolio_id: UUID | None = None
    owner_user_id: UUID | None = None
    health: ProjectHealth = "unknown"
    budget_cents: int = 0
    version: int = 1
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
    milestone_id: UUID | None = None
    assignee_user_id: UUID | None = None
    estimated_minutes: int = 0
    actual_minutes: int = 0
    version: int = 1
    due_date: date | None
    position: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProjectPortfolioCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=10_000)
    objective: str | None = Field(default=None, max_length=500)
    budget_cents: int = Field(default=0, ge=0)


class ProjectPortfolioResponse(StrictSchema):
    id: UUID
    name: str
    description: str | None
    objective: str | None
    budget_cents: int
    is_active: bool
    project_count: int
    active_projects: int
    at_risk_projects: int


class ProjectGovernanceUpdate(StrictSchema):
    portfolio_id: UUID | None = None
    owner_user_id: UUID | None = None
    health: ProjectHealth | None = None
    budget_cents: int | None = Field(default=None, ge=0)
    expected_version: int = Field(ge=1)


class ProjectMilestoneCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=10_000)
    due_date: date


class ProjectMilestoneUpdate(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=10_000)
    due_date: date | None = None
    status: MilestoneStatus | None = None


class ProjectMilestoneResponse(StrictSchema):
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    due_date: date
    status: MilestoneStatus
    completed_at: datetime | None
    task_total: int
    task_done: int


class ProjectRiskCreate(StrictSchema):
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(min_length=2, max_length=10_000)
    mitigation: str | None = Field(default=None, max_length=10_000)
    probability: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)
    owner_user_id: UUID | None = None


class ProjectRiskUpdate(StrictSchema):
    status: RiskStatus | None = None
    mitigation: str | None = Field(default=None, max_length=10_000)
    owner_user_id: UUID | None = None


class ProjectRiskResponse(StrictSchema):
    id: UUID
    project_id: UUID
    owner_user_id: UUID | None
    title: str
    description: str
    mitigation: str | None
    probability: int
    impact: int
    score: int
    status: RiskStatus
    created_at: datetime
    updated_at: datetime


class ProjectMemberCreate(StrictSchema):
    user_id: UUID
    role: str = Field(default="Membro", min_length=2, max_length=120)
    allocation_percent: int = Field(default=100, ge=1, le=100)


class ProjectMemberResponse(StrictSchema):
    id: UUID
    project_id: UUID
    user_id: UUID
    role: str
    allocation_percent: int


class ProjectTaskPlanningUpdate(StrictSchema):
    assignee_user_id: UUID | None = None
    milestone_id: UUID | None = None
    estimated_minutes: int | None = Field(default=None, ge=0)
    actual_minutes: int | None = Field(default=None, ge=0)
    expected_version: int = Field(ge=1)


class ProjectTaskDependencyCreate(StrictSchema):
    predecessor_task_id: UUID
    successor_task_id: UUID


class ProjectTaskDependencyResponse(StrictSchema):
    id: UUID
    project_id: UUID
    predecessor_task_id: UUID
    successor_task_id: UUID


class ProjectPortfolioSummary(StrictSchema):
    portfolio_count: int
    project_count: int
    active_projects: int
    overdue_projects: int
    at_risk_projects: int
    open_risks: int
    critical_risks: int
    milestone_count: int
    overdue_milestones: int
    planned_minutes: int
    actual_minutes: int
