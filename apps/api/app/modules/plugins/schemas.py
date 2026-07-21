from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PluginResponse(BaseModel):
    id: UUID
    code: str
    name: str
    version: str
    description: str
    authentication_type: str
    catalog_status: str
    company_status: str
    configuration: dict[str, Any]
    manifest: dict[str, Any]


class CompanyPluginUpdate(BaseModel):
    status: Literal["active", "inactive"]
    configuration: dict[str, Any] | None = None


class CredentialCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    values: dict[str, Any]
    expires_at: datetime | None = None


class CredentialResponse(BaseModel):
    id: UUID
    plugin_id: UUID
    name: str
    status: str
    masked_values: dict[str, str]
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConnectionTestResponse(BaseModel):
    test_id: UUID
    success: bool
    message: str
    duration_ms: int
    tested_at: datetime


class CredentialRotationResponse(BaseModel):
    rotated: int
    failed: int


class ConnectionTestHistoryResponse(BaseModel):
    id: UUID
    plugin_id: UUID
    credential_id: UUID | None
    success: bool
    message: str
    duration_ms: int
    created_at: datetime


class ManagedVaultMetricResponse(BaseModel):
    provider_code: str
    provider_name: str
    total_tests: int
    successful_tests: int
    failed_tests: int
    success_rate: float
    average_duration_ms: int
    last_tested_at: datetime | None
