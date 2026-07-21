from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from typing import Any
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
from app.modules.metadata.formula_engine import validate_formula_contracts
from app.modules.metadata.models import (
    MetadataEntityDefinition,
    MetadataEntityVersion,
    MetadataFieldDefinition,
    MetadataFormulaDefinition,
    MetadataLayoutDefinition,
    MetadataRecordTypeDefinition,
    MetadataRelationshipDefinition,
    MetadataValidationRule,
    MetadataViewDefinition,
)
from app.modules.metadata.repository import (
    entity_key_exists,
    get_entity_definition,
    get_entity_version,
    list_entity_definitions,
    list_version_fields,
)
from app.modules.metadata.schemas import (
    MetadataDesignResponse,
    MetadataDesignUpdate,
    MetadataEntityCreate,
    MetadataEntityDetail,
    MetadataEntityDraftUpdate,
    MetadataEntitySummary,
    MetadataEntityVersionResponse,
    MetadataFieldInput,
    MetadataFieldResponse,
    MetadataFormulaInput,
    MetadataLayoutInput,
    MetadataLayoutSectionInput,
    MetadataRecordTypeInput,
    MetadataRelationshipInput,
    MetadataValidationResponse,
    MetadataValidationRuleInput,
    MetadataViewInput,
)
from app.modules.metadata.view_engine import validate_view_contract

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


def _default_design(fields: Sequence[MetadataFieldDefinition]) -> MetadataDesignUpdate:
    field_keys = [field.key for field in sorted(fields, key=lambda item: item.position)]
    return MetadataDesignUpdate(
        layouts=[
            MetadataLayoutInput(
                key="default_layout",
                label="Formulario principal",
                is_default=True,
                sections=[
                    MetadataLayoutSectionInput(
                        key="main_section",
                        label="Informacoes principais",
                        fields=field_keys,
                        columns=2,
                    )
                ],
            )
        ],
        views=[
            MetadataViewInput(
                key="default_view",
                label="Lista principal",
                columns=field_keys[: min(6, len(field_keys))],
                is_default=True,
            )
        ],
        record_types=[
            MetadataRecordTypeInput(
                key="default",
                label="Padrao",
                layout_key="default_layout",
                is_default=True,
            )
        ],
    )


def _canonical_design(payload: MetadataDesignUpdate) -> MetadataDesignUpdate:
    if payload.record_types:
        return payload
    default_layout = next(item for item in payload.layouts if item.is_default)
    return payload.model_copy(
        update={
            "record_types": [
                MetadataRecordTypeInput(
                    key="default",
                    label="Padrao",
                    layout_key=default_layout.key,
                    is_default=True,
                )
            ]
        }
    )


def calculate_design_checksum(payload: MetadataDesignUpdate) -> str:
    serialized = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_design_contracts(
    payload: MetadataDesignUpdate, fields: Sequence[MetadataFieldDefinition]
) -> list[str]:
    errors: list[str] = []
    field_keys = {field.key for field in fields}
    field_types = {field.key: field.data_type for field in fields}
    for layout in payload.layouts:
        referenced = {field_key for section in layout.sections for field_key in section.fields}
        unknown = sorted(referenced - field_keys)
        if unknown:
            errors.append(
                f"O layout '{layout.key}' usa campos desconhecidos: {', '.join(unknown)}."
            )
    for view in payload.views:
        referenced = set(view.columns)
        referenced.update(item.field_key for item in view.filters)
        referenced.update(item.field_key for item in view.sorting)
        unknown = sorted(referenced - field_keys)
        if unknown:
            errors.append(
                f"A visualizacao '{view.key}' usa campos desconhecidos: {', '.join(unknown)}."
            )
        errors.extend(validate_view_contract(view, field_types))
    for rule in payload.validation_rules:
        if rule.field_key not in field_keys:
            errors.append(f"A regra '{rule.key}' usa o campo desconhecido '{rule.field_key}'.")
    layout_keys = {layout.key for layout in payload.layouts}
    for record_type in payload.record_types:
        if record_type.layout_key not in layout_keys:
            errors.append(
                f"O tipo de registro '{record_type.key}' usa o layout desconhecido "
                f"'{record_type.layout_key}'."
            )
    field_by_key = {field.key: field for field in fields}
    formula_targets = {formula.target_field_key for formula in payload.formulas if formula.active}
    for relationship in payload.relationships:
        source = field_by_key.get(relationship.source_field_key)
        if source is None:
            errors.append(
                f"O relacionamento '{relationship.key}' usa o campo desconhecido "
                f"'{relationship.source_field_key}'."
            )
        elif source.data_type != "uuid":
            errors.append(f"O relacionamento '{relationship.key}' exige um campo UUID.")
        elif relationship.source_field_key in formula_targets:
            errors.append(f"O relacionamento '{relationship.key}' nao pode usar campo calculado.")
        elif relationship.relationship_type == "one_to_one" and not source.unique_values:
            errors.append(
                f"O relacionamento individual '{relationship.key}' exige campo com valor unico."
            )
    errors.extend(validate_formula_contracts(payload.formulas, fields))
    return errors


async def _validate_relationship_targets(
    database: AsyncSession,
    company_id: UUID,
    definition_id: UUID,
    relationships: Sequence[MetadataRelationshipInput],
) -> list[str]:
    errors: list[str] = []
    for relationship in relationships:
        target = await get_entity_definition(
            database, company_id, relationship.target_definition_id
        )
        if target is None:
            errors.append(f"O relacionamento '{relationship.key}' possui destino indisponivel.")
        elif target.id != definition_id and target.published_version is None:
            errors.append(
                f"O relacionamento '{relationship.key}' exige uma entidade de destino publicada."
            )
    return errors


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _decimal_compare(left: Any, right: Any, operator: str) -> bool:
    try:
        left_value = Decimal(str(left))
        right_value = Decimal(str(right))
    except (InvalidOperation, TypeError, ValueError):
        return False
    return left_value > right_value if operator == "greater_than" else left_value < right_value


def evaluate_record_validation_rules(
    rules: Sequence[MetadataValidationRuleInput], values: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    for rule in rules:
        if not rule.active:
            continue
        value = values.get(rule.field_key)
        expected = rule.comparison_value
        valid = True
        if rule.operator == "equals":
            valid = value == expected
        elif rule.operator == "not_equals":
            valid = value != expected
        elif rule.operator in {"greater_than", "less_than"}:
            valid = _decimal_compare(value, expected, rule.operator)
        elif rule.operator == "contains":
            valid = isinstance(value, (str, list, dict)) and expected in value
        elif rule.operator == "is_empty":
            valid = _is_empty(value)
        elif rule.operator == "is_not_empty":
            valid = not _is_empty(value)
        if not valid:
            errors.append(rule.message)
    return errors


async def _load_design_rows(
    database: AsyncSession, company_id: UUID, version_id: UUID
) -> tuple[
    list[MetadataLayoutDefinition],
    list[MetadataViewDefinition],
    list[MetadataValidationRule],
    list[MetadataRelationshipDefinition],
    list[MetadataFormulaDefinition],
    list[MetadataRecordTypeDefinition],
]:
    layouts = list(
        (
            await database.scalars(
                select(MetadataLayoutDefinition)
                .where(
                    MetadataLayoutDefinition.company_id == company_id,
                    MetadataLayoutDefinition.version_id == version_id,
                )
                .order_by(MetadataLayoutDefinition.key)
            )
        ).all()
    )
    views = list(
        (
            await database.scalars(
                select(MetadataViewDefinition)
                .where(
                    MetadataViewDefinition.company_id == company_id,
                    MetadataViewDefinition.version_id == version_id,
                )
                .order_by(MetadataViewDefinition.key)
            )
        ).all()
    )
    rules = list(
        (
            await database.scalars(
                select(MetadataValidationRule)
                .where(
                    MetadataValidationRule.company_id == company_id,
                    MetadataValidationRule.version_id == version_id,
                )
                .order_by(MetadataValidationRule.key)
            )
        ).all()
    )
    relationships = list(
        await database.scalars(
            select(MetadataRelationshipDefinition)
            .where(
                MetadataRelationshipDefinition.company_id == company_id,
                MetadataRelationshipDefinition.version_id == version_id,
            )
            .order_by(MetadataRelationshipDefinition.key)
        )
    )
    formulas = list(
        await database.scalars(
            select(MetadataFormulaDefinition)
            .where(
                MetadataFormulaDefinition.company_id == company_id,
                MetadataFormulaDefinition.version_id == version_id,
            )
            .order_by(MetadataFormulaDefinition.key)
        )
    )
    record_types = list(
        await database.scalars(
            select(MetadataRecordTypeDefinition)
            .where(
                MetadataRecordTypeDefinition.company_id == company_id,
                MetadataRecordTypeDefinition.version_id == version_id,
            )
            .order_by(MetadataRecordTypeDefinition.key)
        )
    )
    return layouts, views, rules, relationships, formulas, record_types


def _design_from_rows(
    layouts: Sequence[MetadataLayoutDefinition],
    views: Sequence[MetadataViewDefinition],
    rules: Sequence[MetadataValidationRule],
    relationships: Sequence[MetadataRelationshipDefinition],
    formulas: Sequence[MetadataFormulaDefinition],
    record_types: Sequence[MetadataRecordTypeDefinition],
) -> MetadataDesignUpdate:
    return MetadataDesignUpdate(
        layouts=[
            MetadataLayoutInput(
                key=item.key,
                label=item.label,
                sections=item.sections,
                is_default=item.is_default,
            )
            for item in layouts
        ],
        views=[
            MetadataViewInput(
                key=item.key,
                label=item.label,
                columns=item.columns,
                filters=item.filters,
                sorting=item.sorting,
                is_default=item.is_default,
            )
            for item in views
        ],
        validation_rules=[
            MetadataValidationRuleInput(
                key=item.key,
                label=item.label,
                field_key=item.field_key,
                operator=item.operator,
                comparison_value=item.comparison_value,
                message=item.message,
                active=item.active,
            )
            for item in rules
        ],
        relationships=[
            MetadataRelationshipInput(
                key=item.key,
                label=item.label,
                source_field_key=item.source_field_key,
                target_definition_id=item.target_definition_id,
                relationship_type=item.relationship_type,
                on_delete=item.on_delete,
            )
            for item in relationships
        ],
        formulas=[
            MetadataFormulaInput(
                key=item.key,
                label=item.label,
                target_field_key=item.target_field_key,
                expression=item.expression,
                active=item.active,
            )
            for item in formulas
        ],
        record_types=[
            MetadataRecordTypeInput(
                key=item.key,
                label=item.label,
                description=item.description,
                layout_key=item.layout_key,
                is_default=item.is_default,
                active=item.active,
            )
            for item in record_types
        ],
    )


async def _load_design(
    database: AsyncSession,
    company_id: UUID,
    version: MetadataEntityVersion,
    fields: Sequence[MetadataFieldDefinition],
) -> tuple[MetadataDesignUpdate, bool]:
    rows = await _load_design_rows(database, company_id, version.id)
    if not any(rows):
        return _default_design(fields), False
    return _canonical_design(_design_from_rows(*rows)), True


async def _replace_design(
    database: AsyncSession,
    *,
    company_id: UUID,
    version_id: UUID,
    payload: MetadataDesignUpdate,
) -> None:
    payload = _canonical_design(payload)
    for model in (
        MetadataLayoutDefinition,
        MetadataViewDefinition,
        MetadataValidationRule,
        MetadataRelationshipDefinition,
        MetadataFormulaDefinition,
        MetadataRecordTypeDefinition,
    ):
        await database.execute(
            delete(model).where(
                model.company_id == company_id,
                model.version_id == version_id,
            )
        )
    database.add_all(
        [
            MetadataLayoutDefinition(
                company_id=company_id,
                version_id=version_id,
                key=item.key,
                label=item.label,
                sections=[section.model_dump(mode="json") for section in item.sections],
                is_default=item.is_default,
            )
            for item in payload.layouts
        ]
        + [
            MetadataViewDefinition(
                company_id=company_id,
                version_id=version_id,
                key=item.key,
                label=item.label,
                columns=item.columns,
                filters=[entry.model_dump(mode="json") for entry in item.filters],
                sorting=[entry.model_dump(mode="json") for entry in item.sorting],
                is_default=item.is_default,
            )
            for item in payload.views
        ]
        + [
            MetadataValidationRule(
                company_id=company_id,
                version_id=version_id,
                key=item.key,
                label=item.label,
                field_key=item.field_key,
                operator=item.operator,
                comparison_value=item.comparison_value,
                message=item.message,
                active=item.active,
            )
            for item in payload.validation_rules
        ]
        + [
            MetadataRelationshipDefinition(
                company_id=company_id,
                version_id=version_id,
                key=item.key,
                label=item.label,
                source_field_key=item.source_field_key,
                target_definition_id=item.target_definition_id,
                relationship_type=item.relationship_type,
                on_delete=item.on_delete,
            )
            for item in payload.relationships
        ]
        + [
            MetadataFormulaDefinition(
                company_id=company_id,
                version_id=version_id,
                key=item.key,
                label=item.label,
                target_field_key=item.target_field_key,
                expression=item.expression.model_dump(mode="json"),
                active=item.active,
            )
            for item in payload.formulas
        ]
        + [
            MetadataRecordTypeDefinition(
                company_id=company_id,
                version_id=version_id,
                key=item.key,
                label=item.label,
                description=item.description,
                layout_key=item.layout_key,
                is_default=item.is_default,
                active=item.active,
            )
            for item in payload.record_types
        ]
    )


async def validation_rules_for_version(
    database: AsyncSession, company_id: UUID, version_id: UUID
) -> list[MetadataValidationRuleInput]:
    _, _, rules, _, _, _ = await _load_design_rows(database, company_id, version_id)
    return [
        MetadataValidationRuleInput(
            key=item.key,
            label=item.label,
            field_key=item.field_key,
            operator=item.operator,
            comparison_value=item.comparison_value,
            message=item.message,
            active=item.active,
        )
        for item in rules
    ]


async def formulas_for_version(
    database: AsyncSession, company_id: UUID, version_id: UUID
) -> list[MetadataFormulaInput]:
    _, _, _, _, formulas, _ = await _load_design_rows(database, company_id, version_id)
    return [
        MetadataFormulaInput(
            key=item.key,
            label=item.label,
            target_field_key=item.target_field_key,
            expression=item.expression,
            active=item.active,
        )
        for item in formulas
    ]


async def relationships_for_version(
    database: AsyncSession, company_id: UUID, version_id: UUID
) -> list[MetadataRelationshipInput]:
    _, _, _, relationships, _, _ = await _load_design_rows(database, company_id, version_id)
    return [
        MetadataRelationshipInput(
            key=item.key,
            label=item.label,
            source_field_key=item.source_field_key,
            target_definition_id=item.target_definition_id,
            relationship_type=item.relationship_type,
            on_delete=item.on_delete,
        )
        for item in relationships
    ]


async def record_types_for_version(
    database: AsyncSession, company_id: UUID, version_id: UUID
) -> list[MetadataRecordTypeInput]:
    _, _, _, _, _, record_types = await _load_design_rows(database, company_id, version_id)
    return [
        MetadataRecordTypeInput(
            key=item.key,
            label=item.label,
            description=item.description,
            layout_key=item.layout_key,
            is_default=item.is_default,
            active=item.active,
        )
        for item in record_types
    ]


async def incoming_relationships_for_definition(
    database: AsyncSession, company_id: UUID, definition_id: UUID
) -> list[tuple[MetadataRelationshipDefinition, UUID]]:
    rows = await database.execute(
        select(MetadataRelationshipDefinition, MetadataEntityVersion.definition_id)
        .join(
            MetadataEntityVersion,
            MetadataEntityVersion.id == MetadataRelationshipDefinition.version_id,
        )
        .where(
            MetadataRelationshipDefinition.company_id == company_id,
            MetadataRelationshipDefinition.target_definition_id == definition_id,
            MetadataEntityVersion.status == "published",
        )
    )
    return [(relationship, source_id) for relationship, source_id in rows.all()]


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


async def get_design(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    correlation_id: UUID,
) -> MetadataDesignResponse:
    _, version, fields = await _load_current(database, context.company_id, definition_id)
    await _authorize(
        database,
        context,
        correlation_id=correlation_id,
        action="view",
        permission="metadata.view",
        resource_id=definition_id,
    )
    payload, _ = await _load_design(database, context.company_id, version, fields)
    await database.commit()
    return MetadataDesignResponse(
        **payload.model_dump(),
        version=version.version,
        version_status=version.status,
        checksum=calculate_design_checksum(payload),
    )


async def update_design(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    payload: MetadataDesignUpdate,
    correlation_id: UUID,
) -> MetadataDesignResponse:
    entity, version, fields = await _load_current(database, context.company_id, definition_id)
    if version.status != "draft":
        raise MetadataServiceError(
            "Crie uma nova versao antes de alterar layouts, visualizacoes ou regras.",
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
    payload = _canonical_design(payload)
    errors = validate_design_contracts(payload, fields)
    errors.extend(
        await _validate_relationship_targets(
            database, context.company_id, definition_id, payload.relationships
        )
    )
    if errors:
        await database.commit()
        raise MetadataServiceError(" ".join(errors), status_code=422)
    await _replace_design(
        database,
        company_id=context.company_id,
        version_id=version.id,
        payload=payload,
    )
    version.status = "draft"
    version.updated_at = utc_now()
    checksum = calculate_design_checksum(payload)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.design.updated",
        target_type="metadata_entity_definition",
        target_id=entity.id,
        details={
            "version": version.version,
            "layout_count": len(payload.layouts),
            "view_count": len(payload.views),
            "rule_count": len(payload.validation_rules),
            "relationship_count": len(payload.relationships),
            "formula_count": len(payload.formulas),
            "record_type_count": len(payload.record_types),
            "checksum": checksum,
        },
    )
    await _emit(
        database,
        event_type="metadata.design.updated",
        context=context,
        correlation_id=correlation_id,
        entity=entity,
        version=version.version,
    )
    await database.commit()
    return MetadataDesignResponse(
        **payload.model_dump(),
        version=version.version,
        version_status=version.status,
        checksum=checksum,
    )


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
    current_design, _ = await _load_design(database, context.company_id, current, current_fields)
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
    await _replace_design(
        database,
        company_id=context.company_id,
        version_id=version.id,
        payload=current_design,
    )
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
    design, persisted = await _load_design(database, context.company_id, version, fields)
    errors.extend(validate_design_contracts(design, fields))
    errors.extend(
        await _validate_relationship_targets(
            database, context.company_id, definition_id, design.relationships
        )
    )
    if not errors and not persisted:
        await _replace_design(
            database,
            company_id=context.company_id,
            version_id=version.id,
            payload=design,
        )
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


async def views_for_version(
    database: AsyncSession, company_id: UUID, version_id: UUID
) -> list[MetadataViewDefinition]:
    return list(
        await database.scalars(
            select(MetadataViewDefinition)
            .where(
                MetadataViewDefinition.company_id == company_id,
                MetadataViewDefinition.version_id == version_id,
            )
            .order_by(MetadataViewDefinition.is_default.desc(), MetadataViewDefinition.key)
        )
    )
