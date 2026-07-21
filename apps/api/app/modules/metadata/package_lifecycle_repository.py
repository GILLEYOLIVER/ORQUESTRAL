from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.metadata.models import (
    MetadataPackageCatalog,
    MetadataPackageInstallation,
    MetadataPackageVersion,
)


async def get_package_catalog(
    database: AsyncSession, company_id: UUID, package_key: str
) -> MetadataPackageCatalog | None:
    return cast(
        MetadataPackageCatalog | None,
        await database.scalar(
            select(MetadataPackageCatalog).where(
                MetadataPackageCatalog.company_id == company_id,
                MetadataPackageCatalog.key == package_key,
            )
        ),
    )


async def get_package_release(
    database: AsyncSession, company_id: UUID, release_id: UUID
) -> tuple[MetadataPackageCatalog, MetadataPackageVersion] | None:
    row = (
        await database.execute(
            select(MetadataPackageCatalog, MetadataPackageVersion)
            .join(
                MetadataPackageVersion,
                MetadataPackageVersion.package_catalog_id == MetadataPackageCatalog.id,
            )
            .where(
                MetadataPackageCatalog.company_id == company_id,
                MetadataPackageVersion.company_id == company_id,
                MetadataPackageVersion.id == release_id,
            )
        )
    ).first()
    return (row[0], row[1]) if row is not None else None


async def get_package_release_by_version(
    database: AsyncSession,
    company_id: UUID,
    package_key: str,
    version: str,
    *,
    published_only: bool = False,
) -> tuple[MetadataPackageCatalog, MetadataPackageVersion] | None:
    statement = (
        select(MetadataPackageCatalog, MetadataPackageVersion)
        .join(
            MetadataPackageVersion,
            MetadataPackageVersion.package_catalog_id == MetadataPackageCatalog.id,
        )
        .where(
            MetadataPackageCatalog.company_id == company_id,
            MetadataPackageVersion.company_id == company_id,
            MetadataPackageCatalog.key == package_key,
            MetadataPackageVersion.version == version,
        )
    )
    if published_only:
        statement = statement.where(MetadataPackageVersion.status == "published")
    row = (await database.execute(statement)).first()
    return (row[0], row[1]) if row is not None else None


async def list_package_releases(
    database: AsyncSession, company_id: UUID, definition_id: UUID | None
) -> list[tuple[MetadataPackageCatalog, MetadataPackageVersion]]:
    statement = (
        select(MetadataPackageCatalog, MetadataPackageVersion)
        .join(
            MetadataPackageVersion,
            MetadataPackageVersion.package_catalog_id == MetadataPackageCatalog.id,
        )
        .where(
            MetadataPackageCatalog.company_id == company_id,
            MetadataPackageVersion.company_id == company_id,
        )
        .order_by(MetadataPackageCatalog.key, MetadataPackageVersion.created_at.desc())
    )
    if definition_id is not None:
        statement = statement.where(MetadataPackageVersion.entity_definition_id == definition_id)
    result = await database.execute(statement)
    return [(row[0], row[1]) for row in result.all()]


async def get_package_installation(
    database: AsyncSession,
    company_id: UUID,
    package_key: str,
    package_version: str,
    target_environment: str,
) -> MetadataPackageInstallation | None:
    return cast(
        MetadataPackageInstallation | None,
        await database.scalar(
            select(MetadataPackageInstallation).where(
                MetadataPackageInstallation.company_id == company_id,
                MetadataPackageInstallation.package_key == package_key,
                MetadataPackageInstallation.package_version == package_version,
                MetadataPackageInstallation.target_environment == target_environment,
                MetadataPackageInstallation.status == "installed",
            )
        ),
    )


async def list_package_installations(
    database: AsyncSession, company_id: UUID
) -> list[MetadataPackageInstallation]:
    return list(
        (
            await database.scalars(
                select(MetadataPackageInstallation)
                .where(MetadataPackageInstallation.company_id == company_id)
                .order_by(MetadataPackageInstallation.installed_at.desc())
            )
        ).all()
    )
