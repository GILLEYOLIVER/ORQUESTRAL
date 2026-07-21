from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.metadata.models import MetadataRecord


async def list_records(
    database: AsyncSession,
    company_id: UUID,
    definition_id: UUID,
    *,
    page: int,
    page_size: int,
) -> tuple[list[MetadataRecord], int]:
    filters = (
        MetadataRecord.company_id == company_id,
        MetadataRecord.definition_id == definition_id,
        MetadataRecord.deleted_at.is_(None),
    )
    total = int(
        await database.scalar(select(func.count()).select_from(MetadataRecord).where(*filters)) or 0
    )
    records = list(
        await database.scalars(
            select(MetadataRecord)
            .where(*filters)
            .order_by(MetadataRecord.created_at.desc(), MetadataRecord.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return records, total


async def get_record(
    database: AsyncSession,
    company_id: UUID,
    definition_id: UUID,
    record_id: UUID,
) -> MetadataRecord | None:
    record: MetadataRecord | None = await database.scalar(
        select(MetadataRecord).where(
            MetadataRecord.id == record_id,
            MetadataRecord.company_id == company_id,
            MetadataRecord.definition_id == definition_id,
            MetadataRecord.deleted_at.is_(None),
        )
    )
    return record


async def get_record_by_idempotency_key(
    database: AsyncSession,
    company_id: UUID,
    definition_id: UUID,
    idempotency_key: UUID,
) -> MetadataRecord | None:
    record: MetadataRecord | None = await database.scalar(
        select(MetadataRecord).where(
            MetadataRecord.company_id == company_id,
            MetadataRecord.definition_id == definition_id,
            MetadataRecord.idempotency_key == idempotency_key,
            MetadataRecord.deleted_at.is_(None),
        )
    )
    return record


async def unique_value_exists(
    database: AsyncSession,
    company_id: UUID,
    definition_id: UUID,
    field_key: str,
    value: object,
    *,
    excluding_record_id: UUID | None = None,
) -> bool:
    filters = [
        MetadataRecord.company_id == company_id,
        MetadataRecord.definition_id == definition_id,
        MetadataRecord.deleted_at.is_(None),
        MetadataRecord.values[field_key].astext == str(value),
    ]
    if excluding_record_id is not None:
        filters.append(MetadataRecord.id != excluding_record_id)
    return await database.scalar(select(MetadataRecord.id).where(*filters)) is not None
