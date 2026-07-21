from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utc_now
from app.core.tenancy import RequestContext
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.metadata.package_schemas import (
    MetadataEntityPackage,
    MetadataPackageDefinition,
    MetadataPackageImportRequest,
    MetadataPortableDesign,
    MetadataPortableRelationship,
)
from app.modules.metadata.repository import (
    get_entity_definition,
    get_entity_definition_by_key,
)
from app.modules.metadata.schemas import (
    MetadataDesignUpdate,
    MetadataEntityCreate,
    MetadataEntityDetail,
    MetadataRelationshipInput,
)
from app.modules.metadata.service import (
    MetadataServiceError,
    create_entity,
    get_design,
    get_entity,
    update_design,
)


def calculate_package_checksum(definition: MetadataPackageDefinition) -> str:
    serialized = json.dumps(
        definition.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _event(
    database: AsyncSession,
    *,
    event_type: str,
    context: RequestContext,
    correlation_id: UUID,
    definition_id: UUID,
    entity_key: str,
) -> None:
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=event_type,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            correlation_id=correlation_id,
            classification="internal",
            payload={"definition_id": str(definition_id), "entity_key": entity_key},
        ),
    )


async def export_entity_package(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    correlation_id: UUID,
) -> MetadataEntityPackage:
    entity = await get_entity(database, context, definition_id, correlation_id)
    design = await get_design(database, context, definition_id, correlation_id)
    relationships: list[MetadataPortableRelationship] = []
    for item in design.relationships:
        target = await get_entity_definition(
            database, context.company_id, item.target_definition_id
        )
        if target is None:
            raise MetadataServiceError(
                "O pacote possui relacionamento com destino indisponivel.", status_code=409
            )
        relationships.append(
            MetadataPortableRelationship(
                key=item.key,
                label=item.label,
                source_field_key=item.source_field_key,
                target_entity_key=target.key,
                relationship_type=item.relationship_type,
                on_delete=item.on_delete,
            )
        )
    definition = MetadataPackageDefinition(
        key=entity.key,
        label=entity.label,
        plural_label=entity.plural_label,
        description=entity.description,
        fields=entity.version.fields,
        design=MetadataPortableDesign(
            layouts=design.layouts,
            views=design.views,
            validation_rules=design.validation_rules,
            relationships=relationships,
            formulas=design.formulas,
            record_types=design.record_types,
        ),
    )
    package = MetadataEntityPackage(
        exported_at=utc_now(),
        definition=definition,
        checksum=calculate_package_checksum(definition),
    )
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.package.exported",
        target_type="metadata_entity_definition",
        target_id=entity.id,
        details={"entity_key": entity.key, "format_version": package.format_version},
    )
    _event(
        database,
        event_type="metadata.package.exported",
        context=context,
        correlation_id=correlation_id,
        definition_id=entity.id,
        entity_key=entity.key,
    )
    await database.commit()
    return package


async def import_entity_package(
    database: AsyncSession,
    context: RequestContext,
    payload: MetadataPackageImportRequest,
    correlation_id: UUID,
) -> MetadataEntityDetail:
    source = payload.package.definition
    if calculate_package_checksum(source) != payload.package.checksum:
        raise MetadataServiceError("O pacote foi alterado ou esta corrompido.", status_code=422)
    entity_key = payload.key_override or source.key
    if await get_entity_definition_by_key(database, context.company_id, entity_key):
        raise MetadataServiceError("Ja existe uma entidade com a chave informada.", status_code=409)

    targets: dict[str, UUID | None] = {}
    for relationship in source.design.relationships:
        if relationship.target_entity_key == source.key:
            targets[relationship.target_entity_key] = None
            continue
        target = await get_entity_definition_by_key(
            database, context.company_id, relationship.target_entity_key
        )
        if target is None:
            raise MetadataServiceError(
                f"A entidade relacionada '{relationship.target_entity_key}' nao existe "
                "nesta empresa.",
                status_code=422,
            )
        targets[relationship.target_entity_key] = target.id

    created = await create_entity(
        database,
        context,
        MetadataEntityCreate(
            key=entity_key,
            label=payload.label_override or source.label,
            plural_label=payload.plural_label_override or source.plural_label,
            description=source.description,
            fields=source.fields,
        ),
        correlation_id,
    )
    relationships = [
        MetadataRelationshipInput(
            key=item.key,
            label=item.label,
            source_field_key=item.source_field_key,
            target_definition_id=(
                created.id
                if item.target_entity_key == source.key
                else targets[item.target_entity_key]
            ),
            relationship_type=item.relationship_type,
            on_delete=item.on_delete,
        )
        for item in source.design.relationships
    ]
    await update_design(
        database,
        context,
        created.id,
        MetadataDesignUpdate(
            layouts=source.design.layouts,
            views=source.design.views,
            validation_rules=source.design.validation_rules,
            relationships=relationships,
            formulas=source.design.formulas,
            record_types=source.design.record_types,
        ),
        correlation_id,
    )
    imported = await get_entity(database, context, created.id, correlation_id)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.package.imported",
        target_type="metadata_entity_definition",
        target_id=created.id,
        details={"entity_key": entity_key, "source_key": source.key},
    )
    _event(
        database,
        event_type="metadata.package.imported",
        context=context,
        correlation_id=correlation_id,
        definition_id=created.id,
        entity_key=entity_key,
    )
    await database.commit()
    return imported
