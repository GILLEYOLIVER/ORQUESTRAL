from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utc_now
from app.core.tenancy import RequestContext
from app.modules.authorization.policy_schemas import (
    PolicyRequest,
    PolicyResource,
    PolicySubject,
)
from app.modules.authorization.policy_service import evaluate_and_record_policy
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.metadata.models import (
    MetadataEntityDefinition,
    MetadataEntityVersion,
    MetadataFieldDefinition,
)
from app.modules.metadata.repository import (
    entity_key_exists,
    get_entity_definition,
    get_entity_version,
    list_entity_definitions,
    list_version_fields,
)
from app.modules.metadata.schemas import (
    MetadataEntityCreate,
    MetadataEntityDetail,
    MetadataEntityDraftUpdate,
    MetadataEntitySummary,
    MetadataEntityVersionResponse,
    MetadataFieldInput,
    MetadataFieldResponse,
    MetadataValidationResponse,
)

RESERVED_FIELD_KEYS = frozenset({"id", "company_id", "created_at", "updated_at", "deleted_at"})


class MetadataServiceError(Exception):
    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _field_contract(field: MetadataFieldInput) -> dict[str, object]:
    return field.model_dump(mode="json")


def calculate_schema_checksum(fields: Sequence[MetadataFieldInput]) -> str:
    canonical = sorted(
        (_field_contract(field) for field in fields), key=lambda item: str(item["key"])
    )
    serialized = json.dumps(canonical, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_field_contracts(fields: Sequence[MetadataFieldInput]) -> list[str]:
    errors: list[str] = []
    keys = [field.key for field in fields]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        errors.append(f"Campos duplicados: {', '.join(duplicates)}.")
    reserved = sorted(set(keys) & RESERVED_FIELD_KEYS)
    if reserved:
        errors.append(f"Campos reservados: {', '.join(reserved)}.")
    for field in fields:
        if field.required and field.default_value is None and field.data_type == "boolean":
            errors.append(f"O campo booleano obrigatorio '{field.key}' precisa de valor padrao.")
    return errors


async def _authorize(
    database: AsyncSession,
    context: RequestContext,
    *,
    correlation_id: UUID,
    action: str,
    permission: str,
    resource_id: UUID | None = None,
    risk_level: str = "low",
) -> None:
    decision = await evaluate_and_record_policy(
        database,
        PolicyRequest(
            subject=PolicySubject.from_request_context(context),
            resource=PolicyResource(
                company_id=context.company_id,
                resource_type="metadata_entity_definition",
                resource_id=str(resource_id) if resource_id else None,
            ),
            action=action,
            required_permission=permission,
            risk_level=risk_level,
            correlation_id=correlation_id,
        ),
    )
    if decision.requires_approval:
        await database.commit()
        raise MetadataServiceError(
            "A operacao exige aprovacao humana antes de continuar.", status_code=409
        )
    if not decision.allowed:
        await database.commit()
        raise MetadataServiceError("Operacao nao autorizada pela politica.", status_code=403)


def _field_inputs_from_models(
    fields: Sequence[MetadataFieldDefinition],
) -> list[MetadataFieldInput]:
    return [
        MetadataFieldInput(
            key=field.key,
            label=field.label,
            data_type=field.data_type,
            required=field.required,
            unique_values=field.unique_values,
            searchable=field.searchable,
            default_value=field.default_value,
            settings=field.settings,
            position=field.position,
        )
        for field in fields
    ]


def _field_rows(
    *, company_id: UUID, version_id: UUID, fields: Sequence[MetadataFieldInput]
) -> list[MetadataFieldDefinition]:
    return [
        MetadataFieldDefinition(
            company_id=company_id,
            version_id=version_id,
            key=field.key,
            label=field.label,
            data_type=field.data_type,
            required=field.required,
            unique_values=field.unique_values,
            searchable=field.searchable,
            default_value=field.default_value,
            settings=field.settings,
            position=field.position,
        )
        for field in fields
    ]


def _summary(entity: MetadataEntityDefinition) -> MetadataEntitySummary:
    return MetadataEntitySummary(
        id=entity.id,
        key=entity.key,
        label=entity.label,
        plural_label=entity.plural_label,
        status=entity.status,
        current_version=entity.current_version,
        published_version=entity.published_version,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def _detail(
    entity: MetadataEntityDefinition,
    version: MetadataEntityVersion,
    fields: Sequence[MetadataFieldDefinition],
) -> MetadataEntityDetail:
    return MetadataEntityDetail(
        **_summary(entity).model_dump(),
        description=entity.description,
        version=MetadataEntityVersionResponse(
            id=version.id,
            version=version.version,
            status=version.status,
            schema_checksum=version.schema_checksum,
            fields=[
                MetadataFieldResponse(
                    id=field.id,
                    **_field_inputs_from_models((field,))[0].model_dump(),
                )
                for field in fields
            ],
            published_at=version.published_at,
            created_at=version.created_at,
            updated_at=version.updated_at,
        ),
    )


async def _load_current(
    database: AsyncSession, company_id: UUID, definition_id: UUID
) -> tuple[MetadataEntityDefinition, MetadataEntityVersion, list[MetadataFieldDefinition]]:
    entity = await get_entity_definition(database, company_id, definition_id)
    if entity is None:
        raise MetadataServiceError("Definicao nao encontrada.", status_code=404)
    version = await get_entity_version(database, company_id, definition_id, entity.current_version)
    if version is None:
        raise MetadataServiceError("Versao atual inconsistente.", status_code=409)
    fields = await list_version_fields(database, company_id, version.id)
    return entity, version, fields


async def _emit(
    database: AsyncSession,
    *,
    event_type: str,
    context: RequestContext,
    correlation_id: UUID,
    entity: MetadataEntityDefinition,
    version: int,
) -> None:
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=event_type,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            correlation_id=correlation_id,
            classification="internal",
            payload={
                "definition_id": str(entity.id),
                "entity_key": entity.key,
                "version": version,
            },
        ),
    )


async def list_entities(
    database: AsyncSession, context: RequestContext, correlation_id: UUID
) -> list[MetadataEntitySummary]:
    await _authorize(
        database,
        context,
        correlation_id=correlation_id,
        action="list",
        permission="metadata.view",
    )
    entities = await list_entity_definitions(database, context.company_id)
    await database.commit()
    return [_summary(entity) for entity in entities]


async def get_entity(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    correlation_id: UUID,
) -> MetadataEntityDetail:
    entity, version, fields = await _load_current(database, context.company_id, definition_id)
    await _authorize(
        database,
        context,
        correlation_id=correlation_id,
        action="view",
        permission="metadata.view",
        resource_id=definition_id,
    )
    await database.commit()
    return _detail(entity, version, fields)


async def create_entity(
    database: AsyncSession,
    context: RequestContext,
    payload: MetadataEntityCreate,
    correlation_id: UUID,
) -> MetadataEntityDetail:
    await _authorize(
        database,
        context,
        correlation_id=correlation_id,
        action="create",
        permission="metadata.configure",
    )
    errors = validate_field_contracts(payload.fields)
    if errors:
        await database.commit()
        raise MetadataServiceError(" ".join(errors), status_code=422)
    if await entity_key_exists(database, context.company_id, payload.key):
        await database.commit()
        raise MetadataServiceError("Ja existe uma entidade com esta chave.", status_code=409)

    checksum = calculate_schema_checksum(payload.fields)
    entity = MetadataEntityDefinition(
        company_id=context.company_id,
        key=payload.key,
        label=payload.label,
        plural_label=payload.plural_label,
        description=payload.description,
        created_by_user_id=context.user_id,
    )
    database.add(entity)
    await database.flush()
    version = MetadataEntityVersion(
        company_id=context.company_id,
        definition_id=entity.id,
        version=1,
        status="draft",
        schema_checksum=checksum,
        created_by_user_id=context.user_id,
    )
    database.add(version)
    await database.flush()
    fields = _field_rows(
        company_id=context.company_id, version_id=version.id, fields=payload.fields
    )
    database.add_all(fields)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.entity.created",
        target_type="metadata_entity_definition",
        target_id=entity.id,
        details={"entity_key": entity.key, "version": 1},
    )
    await _emit(
        database,
        event_type="metadata.definition.created",
        context=context,
        correlation_id=correlation_id,
        entity=entity,
        version=1,
    )
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise MetadataServiceError(
            "Nao foi possivel criar a definicao sem duplicidade.", status_code=409
        ) from exc
    return _detail(entity, version, fields)


async def update_draft(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    payload: MetadataEntityDraftUpdate,
    correlation_id: UUID,
) -> MetadataEntityDetail:
    entity, version, _ = await _load_current(database, context.company_id, definition_id)
    if version.status != "draft":
        raise MetadataServiceError(
            "Crie uma nova versao antes de alterar uma definicao publicada.",
            status_code=409,
        )
    await _authorize(
        database,
        context,
        correlation_id=correlation_id,
        action="update",
        permission="metadata.configure",
        resource_id=definition_id,
    )
    errors = validate_field_contracts(payload.fields)
    if errors:
        await database.commit()
        raise MetadataServiceError(" ".join(errors), status_code=422)

    changes = payload.model_dump(exclude_unset=True, exclude={"fields"})
    for name, value in changes.items():
        setattr(entity, name, value)
    entity.updated_at = utc_now()
    version.status = "draft"
    version.schema_checksum = calculate_schema_checksum(payload.fields)
    version.updated_at = utc_now()
    await database.execute(
        delete(MetadataFieldDefinition).where(
            MetadataFieldDefinition.company_id == context.company_id,
            MetadataFieldDefinition.version_id == version.id,
        )
    )
    fields = _field_rows(
        company_id=context.company_id, version_id=version.id, fields=payload.fields
    )
    database.add_all(fields)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.entity.draft_updated",
        target_type="metadata_entity_definition",
        target_id=entity.id,
        details={"entity_key": entity.key, "version": version.version},
    )
    await _emit(
        database,
        event_type="metadata.definition.draft_updated",
        context=context,
        correlation_id=correlation_id,
        entity=entity,
        version=version.version,
    )
    await database.commit()
    return _detail(entity, version, fields)


async def create_draft_version(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    correlation_id: UUID,
) -> MetadataEntityDetail:
    entity, current, current_fields = await _load_current(
        database, context.company_id, definition_id
    )
    await _authorize(
        database,
        context,
        correlation_id=correlation_id,
        action="update",
        permission="metadata.configure",
        resource_id=definition_id,
    )
    if current.status == "draft":
        await database.commit()
        raise MetadataServiceError("Ja existe uma versao em rascunho.", status_code=409)
    if entity.published_version is None:
        await database.commit()
        raise MetadataServiceError("A primeira versao ainda nao foi publicada.", status_code=409)

    inputs = _field_inputs_from_models(current_fields)
    next_number = entity.current_version + 1
    version = MetadataEntityVersion(
        company_id=context.company_id,
        definition_id=entity.id,
        version=next_number,
        status="draft",
        schema_checksum=calculate_schema_checksum(inputs),
        created_by_user_id=context.user_id,
    )
    database.add(version)
    await database.flush()
    fields = _field_rows(company_id=context.company_id, version_id=version.id, fields=inputs)
    database.add_all(fields)
    entity.current_version = next_number
    entity.updated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.entity.version_created",
        target_type="metadata_entity_definition",
        target_id=entity.id,
        details={"entity_key": entity.key, "version": next_number},
    )
    await _emit(
        database,
        event_type="metadata.definition.version_created",
        context=context,
        correlation_id=correlation_id,
        entity=entity,
        version=next_number,
    )
    await database.commit()
    return _detail(entity, version, fields)


async def validate_entity(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    correlation_id: UUID,
) -> MetadataValidationResponse:
    entity, version, fields = await _load_current(database, context.company_id, definition_id)
    await _authorize(
        database,
        context,
        correlation_id=correlation_id,
        action="update",
        permission="metadata.configure",
        resource_id=definition_id,
    )
    if version.status == "published":
        await database.commit()
        raise MetadataServiceError("A versao publicada e imutavel.", status_code=409)
    inputs = _field_inputs_from_models(fields)
    errors = validate_field_contracts(inputs)
    checksum = calculate_schema_checksum(inputs)
    version.schema_checksum = checksum
    version.status = "validated" if not errors else "draft"
    version.updated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.entity.validated",
        target_type="metadata_entity_definition",
        target_id=entity.id,
        details={"entity_key": entity.key, "version": version.version, "valid": not errors},
    )
    await _emit(
        database,
        event_type="metadata.definition.validated",
        context=context,
        correlation_id=correlation_id,
        entity=entity,
        version=version.version,
    )
    await database.commit()
    return MetadataValidationResponse(
        entity_id=entity.id,
        version=version.version,
        valid=not errors,
        errors=errors,
        schema_checksum=checksum,
    )


async def publish_entity(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    correlation_id: UUID,
) -> MetadataEntityDetail:
    entity, version, fields = await _load_current(database, context.company_id, definition_id)
    await _authorize(
        database,
        context,
        correlation_id=correlation_id,
        action="publish",
        permission="metadata.publish",
        resource_id=definition_id,
        risk_level="medium",
    )
    if version.status != "validated":
        await database.commit()
        raise MetadataServiceError("Valide a versao antes de publica-la.", status_code=409)
    if entity.published_version is not None:
        previous = await get_entity_version(
            database,
            context.company_id,
            entity.id,
            entity.published_version,
        )
        if previous is not None and previous.id != version.id:
            previous.status = "retired"
            previous.updated_at = utc_now()
    version.status = "published"
    version.published_by_user_id = context.user_id
    version.published_at = utc_now()
    version.updated_at = utc_now()
    entity.status = "published"
    entity.published_version = version.version
    entity.updated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.entity.published",
        target_type="metadata_entity_definition",
        target_id=entity.id,
        details={"entity_key": entity.key, "version": version.version},
    )
    await _emit(
        database,
        event_type="metadata.definition.published",
        context=context,
        correlation_id=correlation_id,
        entity=entity,
        version=version.version,
    )
    await database.commit()
    return _detail(entity, version, fields)


async def count_company_definitions(database: AsyncSession, company_id: UUID) -> int:
    return len(await list_entity_definitions(database, company_id))


async def published_version(
    database: AsyncSession, company_id: UUID, definition_id: UUID
) -> MetadataEntityVersion | None:
    entity = await get_entity_definition(database, company_id, definition_id)
    if entity is None or entity.published_version is None:
        return None
    entity_version: MetadataEntityVersion | None = await database.scalar(
        select(MetadataEntityVersion).where(
            MetadataEntityVersion.company_id == company_id,
            MetadataEntityVersion.definition_id == definition_id,
            MetadataEntityVersion.version == entity.published_version,
            MetadataEntityVersion.status == "published",
        )
    )
    return entity_version
