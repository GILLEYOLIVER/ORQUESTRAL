from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.metadata.models import (
    MetadataEntityDefinition,
    MetadataEntityVersion,
    MetadataFieldDefinition,
)


async def list_entity_definitions(
    database: AsyncSession, company_id: UUID
) -> list[MetadataEntityDefinition]:
    return list(
        await database.scalars(
            select(MetadataEntityDefinition)
            .where(MetadataEntityDefinition.company_id == company_id)
            .order_by(MetadataEntityDefinition.label, MetadataEntityDefinition.id)
        )
    )


async def get_entity_definition(
    database: AsyncSession, company_id: UUID, definition_id: UUID
) -> MetadataEntityDefinition | None:
    entity: MetadataEntityDefinition | None = await database.scalar(
        select(MetadataEntityDefinition).where(
            MetadataEntityDefinition.id == definition_id,
            MetadataEntityDefinition.company_id == company_id,
        )
    )
    return entity


async def entity_key_exists(database: AsyncSession, company_id: UUID, key: str) -> bool:
    return (
        await database.scalar(
            select(MetadataEntityDefinition.id).where(
                MetadataEntityDefinition.company_id == company_id,
                MetadataEntityDefinition.key == key,
            )
        )
        is not None
    )


async def get_entity_version(
    database: AsyncSession,
    company_id: UUID,
    definition_id: UUID,
    version: int,
) -> MetadataEntityVersion | None:
    entity_version: MetadataEntityVersion | None = await database.scalar(
        select(MetadataEntityVersion).where(
            MetadataEntityVersion.company_id == company_id,
            MetadataEntityVersion.definition_id == definition_id,
            MetadataEntityVersion.version == version,
        )
    )
    return entity_version


async def list_version_fields(
    database: AsyncSession, company_id: UUID, version_id: UUID
) -> list[MetadataFieldDefinition]:
    return list(
        await database.scalars(
            select(MetadataFieldDefinition)
            .where(
                MetadataFieldDefinition.company_id == company_id,
                MetadataFieldDefinition.version_id == version_id,
            )
            .order_by(MetadataFieldDefinition.position, MetadataFieldDefinition.key)
        )
    )
