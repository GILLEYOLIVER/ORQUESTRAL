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


class PluginPublisherCreate(BaseModel):
    code: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9._-]+$")
    name: str = Field(min_length=2, max_length=120)
    public_key: str = Field(min_length=40, max_length=128)


class PluginPublisherResponse(BaseModel):
    id: UUID
    code: str
    name: str
    key_fingerprint: str
    status: str
    created_at: datetime


class PluginPackagePublish(BaseModel):
    publisher_code: str = Field(min_length=2, max_length=80)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?$")
    manifest: dict[str, Any]
    artifact_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    signature: str = Field(min_length=40, max_length=128)
    min_platform_version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?$")
    max_platform_version: str | None = Field(
        default=None, pattern=r"^\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?$"
    )
    requested_permissions: list[str] = Field(default_factory=list, max_length=100)


class PluginPackageVersionResponse(BaseModel):
    id: UUID
    plugin_id: UUID
    publisher_code: str
    version: str
    manifest: dict[str, Any]
    artifact_digest: str
    key_fingerprint: str
    min_platform_version: str
    max_platform_version: str | None
    requested_permissions: list[str]
    status: str
    published_at: datetime


class PluginInstallationRequest(BaseModel):
    version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?$")


class PluginInstallationResponse(BaseModel):
    id: UUID
    plugin_code: str
    version: str
    previous_version: str | None
    operation: str
    status: str
    installed_at: datetime
