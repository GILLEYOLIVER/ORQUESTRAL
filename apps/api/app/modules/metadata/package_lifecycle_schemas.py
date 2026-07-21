from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.schemas import StrictSchema
from app.modules.metadata.package_schemas import MetadataEntityPackage

PackageEnvironment = Literal["local", "testing", "development", "staging", "production"]
PackageReleaseStatus = Literal["draft", "validated", "published", "retired"]
PackageInstallationStatus = Literal["installed", "removed"]
SEMVER_PATTERN = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$"


class MetadataPackageDependency(StrictSchema):
    package_key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    version: str = Field(min_length=5, max_length=32, pattern=SEMVER_PATTERN)
    optional: bool = False


class MetadataPackageReleaseCreate(StrictSchema):
    definition_id: UUID
    version: str = Field(min_length=5, max_length=32, pattern=SEMVER_PATTERN)
    package_key: str | None = Field(
        default=None, min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$"
    )
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2_000)
    dependencies: list[MetadataPackageDependency] = Field(default_factory=list, max_length=30)

    @field_validator("package_key", "display_name", "description")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def dependencies_are_unique(self) -> MetadataPackageReleaseCreate:
        identities = [(item.package_key, item.version) for item in self.dependencies]
        if len(identities) != len(set(identities)):
            raise ValueError("Dependencias duplicadas nao sao permitidas.")
        return self


class MetadataPackageManifest(StrictSchema):
    package_key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2_000)
    version: str = Field(min_length=5, max_length=32, pattern=SEMVER_PATTERN)
    source_environment: PackageEnvironment
    dependencies: list[MetadataPackageDependency] = Field(default_factory=list, max_length=30)


class MetadataPackageReleaseBundle(StrictSchema):
    format_version: Literal["2.0"] = "2.0"
    created_at: datetime
    manifest: MetadataPackageManifest
    artifact: MetadataEntityPackage
    checksum: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")


class MetadataPackageReleaseResponse(StrictSchema):
    id: UUID
    package_catalog_id: UUID
    entity_definition_id: UUID
    package_key: str
    display_name: str
    description: str | None
    version: str
    status: PackageReleaseStatus
    source_environment: PackageEnvironment
    dependencies: list[MetadataPackageDependency]
    checksum: str
    created_at: datetime
    published_at: datetime | None


class MetadataPackageValidationResponse(StrictSchema):
    release: MetadataPackageReleaseResponse
    valid: bool
    errors: list[str]
    warnings: list[str]


class MetadataPackageInstallPreviewRequest(StrictSchema):
    bundle: MetadataPackageReleaseBundle
    target_environment: PackageEnvironment
    key_override: str | None = Field(
        default=None, min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$"
    )


class MetadataPackageInstallPreview(StrictSchema):
    can_install: bool
    package_key: str
    version: str
    target_environment: PackageEnvironment
    actions: list[str]
    blockers: list[str]
    warnings: list[str]
    resolved_dependencies: list[str]
    plan_checksum: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")


class MetadataPackageInstallRequest(MetadataPackageInstallPreviewRequest):
    plan_checksum: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")


class MetadataPackageInstallationResponse(StrictSchema):
    id: UUID
    package_key: str
    package_version: str
    source_checksum: str
    target_environment: PackageEnvironment
    status: PackageInstallationStatus
    installed_definition_id: UUID | None
    installed_at: datetime


class MetadataPackagePromotionRequest(StrictSchema):
    target_environment: PackageEnvironment


class MetadataPackagePromotionResponse(StrictSchema):
    allowed: bool
    source_environment: PackageEnvironment
    target_environment: PackageEnvironment
    blockers: list[str]
    instructions: str
    bundle: MetadataPackageReleaseBundle | None
