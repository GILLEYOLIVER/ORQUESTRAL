from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.schemas import StrictSchema

WorkflowStatus = Literal["draft", "active", "inactive", "error"]
WorkflowSyncStatus = Literal["pending", "synced", "error"]
ExecutionStatus = Literal["queued", "running", "success", "error", "canceled", "waiting"]


class WorkflowCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    definition: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Informe um nome válido.")
        return normalized


class WorkflowUpdate(StrictSchema):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    definition: dict[str, Any] | None = None
    change_summary: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def require_change(self) -> WorkflowUpdate:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos uma alteração.")
        return self


class WorkflowResponse(StrictSchema):
    id: UUID
    name: str
    description: str | None
    definition: dict[str, Any]
    version: int
    status: WorkflowStatus
    sync_status: WorkflowSyncStatus
    webhook_url: str
    last_error: str | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkflowCreatedResponse(WorkflowResponse):
    webhook_secret: str


class WorkflowExecuteRequest(StrictSchema):
    input: dict[str, Any] = Field(default_factory=dict)


class WorkflowExecutionResponse(StrictSchema):
    id: UUID
    workflow_id: UUID
    source: str
    status: ExecutionStatus
    input_summary: dict[str, Any]
    output_summary: dict[str, Any]
    error_summary: str | None
    duration_ms: int | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class WorkflowExportResponse(StrictSchema):
    format: Literal["orkestral.workflow.v1"] = "orkestral.workflow.v1"
    name: str
    description: str | None
    version: int
    definition: dict[str, Any]


class WorkflowWebhookSecretResponse(StrictSchema):
    webhook_url: str
    webhook_secret: str


class WorkflowEngineStatusResponse(StrictSchema):
    configured: bool
    available: bool
    message: str


class WorkflowDefinitionRequest(StrictSchema):
    definition: dict[str, Any] | None = None


class WorkflowValidationIssue(StrictSchema):
    severity: Literal["error", "warning"]
    code: str
    message: str
    node_id: str | None = None


class WorkflowValidationResponse(StrictSchema):
    valid: bool
    issues: list[WorkflowValidationIssue]


class WorkflowVersionResponse(StrictSchema):
    id: UUID
    version: int
    name: str
    description: str | None
    definition: dict[str, Any]
    change_summary: str | None
    created_at: datetime


class WorkflowComparisonResponse(StrictSchema):
    from_version: int
    to_version: int
    added_nodes: list[str]
    removed_nodes: list[str]
    changed_nodes: list[str]
    connections_changed: bool
