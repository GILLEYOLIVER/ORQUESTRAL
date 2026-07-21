from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Date, DateTime, Integer, Numeric, and_, cast, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.metadata.models import MetadataRecord, MetadataRecordShare
from app.modules.metadata.view_engine import (
    MetadataRecordFilterSpec,
    MetadataRecordSortSpec,
)


def _typed_value(field_key: str, data_type: str) -> Any:
    text = MetadataRecord.values[field_key].astext
    if data_type == "integer":
        return cast(text, Integer())
    if data_type == "decimal":
        return cast(text, Numeric)
    if data_type == "date":
        return cast(text, Date())
    if data_type == "datetime":
        return cast(text, DateTime(timezone=True))
    return text


def _text_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _comparison_value(spec: MetadataRecordFilterSpec) -> object:
    if spec.data_type == "integer":
        return int(str(spec.value))
    if spec.data_type == "decimal":
        return Decimal(str(spec.value))
    if spec.data_type == "date":
        return date.fromisoformat(str(spec.value))
    if spec.data_type == "datetime":
        return datetime.fromisoformat(str(spec.value).replace("Z", "+00:00"))
    return _text_value(spec.value)


def _filter_expression(spec: MetadataRecordFilterSpec) -> Any:
    text = MetadataRecord.values[spec.field_key].astext
    typed = _typed_value(spec.field_key, spec.data_type)
    if spec.operator == "is_empty":
        return or_(text.is_(None), text == "")
    if spec.operator == "is_not_empty":
        return and_(text.is_not(None), text != "")
    if spec.operator == "contains":
        escaped = _text_value(spec.value).replace("\\", "\\\\").replace("%", "\\%")
        escaped = escaped.replace("_", "\\_")
        return text.ilike(f"%{escaped}%", escape="\\")
    value = _comparison_value(spec)
    if spec.operator == "equals":
        return typed == value
    if spec.operator == "not_equals":
        return and_(text.is_not(None), typed != value)
    if spec.operator == "greater_than":
        return typed > value
    return typed < value


async def list_records(
    database: AsyncSession,
    company_id: UUID,
    definition_id: UUID,
    *,
    page: int,
    page_size: int,
    view_filters: Sequence[MetadataRecordFilterSpec] = (),
    view_sorting: Sequence[MetadataRecordSortSpec] = (),
    access_scope: str = "all",
    actor_user_id: UUID | None = None,
    role_ids: Sequence[UUID] = (),
) -> tuple[list[MetadataRecord], int]:
    filters: list[Any] = [
        MetadataRecord.company_id == company_id,
        MetadataRecord.definition_id == definition_id,
        MetadataRecord.deleted_at.is_(None),
    ]
    if access_scope != "all" and actor_user_id is not None:
        owner_filter = MetadataRecord.owner_user_id == actor_user_id
        if access_scope == "owned_shared":
            subject_filters = [
                and_(
                    MetadataRecordShare.subject_type == "user",
                    MetadataRecordShare.subject_id == actor_user_id,
                )
            ]
            if role_ids:
                subject_filters.append(
                    and_(
                        MetadataRecordShare.subject_type == "role",
                        MetadataRecordShare.subject_id.in_(role_ids),
                    )
                )
            shared_filter = exists(
                select(MetadataRecordShare.id).where(
                    MetadataRecordShare.company_id == company_id,
                    MetadataRecordShare.definition_id == definition_id,
                    MetadataRecordShare.record_id == MetadataRecord.id,
                    MetadataRecordShare.can_view.is_(True),
                    or_(*subject_filters),
                )
            )
            filters.append(or_(owner_filter, shared_filter))
        else:
            filters.append(owner_filter)
    filters.extend(_filter_expression(item) for item in view_filters)
    total = int(
        await database.scalar(select(func.count()).select_from(MetadataRecord).where(*filters)) or 0
    )
    ordering: list[Any] = [
        (
            _typed_value(item.field_key, item.data_type).desc().nullslast()
            if item.direction == "desc"
            else _typed_value(item.field_key, item.data_type).asc().nullslast()
        )
        for item in view_sorting
    ]
    if not ordering:
        ordering.append(MetadataRecord.created_at.desc())
    ordering.append(MetadataRecord.id.asc())
    records = list(
        await database.scalars(
            select(MetadataRecord)
            .where(*filters)
            .order_by(*ordering)
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


async def relationship_reference_exists(
    database: AsyncSession,
    company_id: UUID,
    source_definition_id: UUID,
    field_key: str,
    target_record_id: UUID,
) -> bool:
    return (
        await database.scalar(
            select(MetadataRecord.id).where(
                MetadataRecord.company_id == company_id,
                MetadataRecord.definition_id == source_definition_id,
                MetadataRecord.deleted_at.is_(None),
                MetadataRecord.values[field_key].astext == str(target_record_id),
            )
        )
        is not None
    )
