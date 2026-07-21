from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from math import ceil
from typing import Literal, cast
from uuid import UUID

from pydantic import AnyUrl, EmailStr, JsonValue, TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utc_now
from app.core.tenancy import RequestContext
from app.modules.authorization.policy_schemas import (
    PolicyDecision,
    PolicyRequest,
    PolicyResource,
    PolicySubject,
)
from app.modules.authorization.policy_service import evaluate_and_record_policy
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.metadata.formula_engine import apply_formulas
from app.modules.metadata.models import (
    MetadataEntityDefinition,
    MetadataEntityVersion,
    MetadataFieldDefinition,
    MetadataRecord,
    MetadataRecordRevision,
    MetadataViewDefinition,
)
from app.modules.metadata.record_repository import (
    get_record,
    get_record_by_idempotency_key,
    list_records,
    relationship_reference_exists,
    unique_value_exists,
)
from app.modules.metadata.record_schemas import (
    MetadataRecordCreate,
    MetadataRecordPage,
    MetadataRecordResponse,
    MetadataRecordUpdate,
)
from app.modules.metadata.repository import get_entity_definition, list_version_fields
from app.modules.metadata.schemas import MetadataViewInput
from app.modules.metadata.security_service import (
    MetadataAccessDecision,
    evaluate_metadata_access,
    record_is_accessible,
)
from app.modules.metadata.service import (
    MetadataServiceError,
    evaluate_record_validation_rules,
    formulas_for_version,
    incoming_relationships_for_definition,
    published_version,
    record_types_for_version,
    relationships_for_version,
    validation_rules_for_version,
    views_for_version,
)
from app.modules.metadata.view_engine import (
    VALUELESS_OPERATORS,
    MetadataFieldType,
    MetadataRecordFilterSpec,
    MetadataRecordSortSpec,
    validate_view_contract,
)

PolicyAction = Literal["view", "list", "create", "update", "delete"]
EMAIL_ADAPTER = TypeAdapter(EmailStr)
URL_ADAPTER = TypeAdapter(AnyUrl)


def _integer_setting(settings: Mapping[str, JsonValue], key: str) -> int | None:
    value = settings.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _normalize_value(field: MetadataFieldDefinition, value: JsonValue) -> JsonValue:
    if value is None:
        if field.required:
            raise ValueError(f"O campo '{field.key}' e obrigatorio.")
        return None
    if field.data_type in {"text", "long_text", "phone"}:
        if not isinstance(value, str):
            raise ValueError(f"O campo '{field.key}' deve ser texto.")
        minimum = _integer_setting(field.settings, "min_length")
        maximum = _integer_setting(field.settings, "max_length")
        if minimum is not None and len(value) < minimum:
            raise ValueError(f"O campo '{field.key}' e menor que o permitido.")
        if maximum is not None and len(value) > maximum:
            raise ValueError(f"O campo '{field.key}' e maior que o permitido.")
        return value
    if field.data_type == "email":
        try:
            return str(EMAIL_ADAPTER.validate_python(value))
        except ValidationError as exc:
            raise ValueError(f"O campo '{field.key}' deve conter um e-mail valido.") from exc
    if field.data_type == "url":
        try:
            return str(URL_ADAPTER.validate_python(value))
        except ValidationError as exc:
            raise ValueError(f"O campo '{field.key}' deve conter uma URL valida.") from exc
    if field.data_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"O campo '{field.key}' deve ser inteiro.")
        return value
    if field.data_type == "decimal":
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError(f"O campo '{field.key}' deve ser decimal.")
        try:
            decimal = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"O campo '{field.key}' deve ser decimal.") from exc
        if not decimal.is_finite():
            raise ValueError(f"O campo '{field.key}' deve ser decimal finito.")
        return format(decimal, "f")
    if field.data_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"O campo '{field.key}' deve ser booleano.")
        return value
    if field.data_type == "date":
        if not isinstance(value, str):
            raise ValueError(f"O campo '{field.key}' deve usar data ISO.")
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError as exc:
            raise ValueError(f"O campo '{field.key}' deve usar data ISO.") from exc
    if field.data_type == "datetime":
        if not isinstance(value, str):
            raise ValueError(f"O campo '{field.key}' deve usar data e hora ISO.")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"O campo '{field.key}' deve usar data e hora ISO.") from exc
        if parsed.tzinfo is None:
            raise ValueError(f"O campo '{field.key}' deve informar fuso horario.")
        return parsed.isoformat()
    if field.data_type == "uuid":
        try:
            return str(UUID(str(value)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"O campo '{field.key}' deve conter UUID valido.") from exc
    return value


def normalize_record_values(
    fields: Sequence[MetadataFieldDefinition],
    values: Mapping[str, JsonValue],
    *,
    computed_field_keys: frozenset[str] = frozenset(),
) -> tuple[dict[str, JsonValue], list[str]]:
    field_by_key = {field.key: field for field in fields}
    errors = [f"Campo desconhecido: {key}." for key in sorted(set(values) - set(field_by_key))]
    errors.extend(
        f"O campo calculado '{key}' nao aceita valor manual."
        for key in sorted(set(values) & computed_field_keys)
    )
    normalized: dict[str, JsonValue] = {}
    for field in fields:
        if field.key in computed_field_keys:
            continue
        if field.key not in values:
            if field.default_value is not None:
                normalized[field.key] = field.default_value
            elif field.required:
                errors.append(f"O campo '{field.key}' e obrigatorio.")
            continue
        try:
            normalized[field.key] = _normalize_value(field, values[field.key])
        except ValueError as exc:
            errors.append(str(exc))
    return normalized, errors


async def _prepare_record_values(
    database: AsyncSession,
    company_id: UUID,
    version: MetadataEntityVersion,
    fields: Sequence[MetadataFieldDefinition],
    values: Mapping[str, JsonValue],
) -> tuple[dict[str, JsonValue], list[str]]:
    formulas = await formulas_for_version(database, company_id, version.id)
    computed = frozenset(item.target_field_key for item in formulas if item.active)
    normalized, errors = normalize_record_values(fields, values, computed_field_keys=computed)
    if errors:
        return normalized, errors
    try:
        calculated = apply_formulas(formulas, normalized)
        field_by_key = {field.key: field for field in fields}
        for key in computed:
            if key in calculated:
                normalized[key] = _normalize_value(field_by_key[key], calculated[key])
    except ValueError as exc:
        errors.append(str(exc))
    return normalized, errors


async def _resolve_record_type(
    database: AsyncSession,
    company_id: UUID,
    version_id: UUID,
    requested: str | None,
) -> str | None:
    record_types = await record_types_for_version(database, company_id, version_id)
    if not record_types:
        return None
    chosen = (
        next(
            (item for item in record_types if item.active and item.key == requested),
            None,
        )
        if requested
        else next((item for item in record_types if item.active and item.is_default), None)
    )
    if chosen is None:
        raise MetadataServiceError("Tipo de registro indisponivel.", status_code=422)
    return chosen.key


async def _validate_relationship_values(
    database: AsyncSession,
    company_id: UUID,
    version_id: UUID,
    values: Mapping[str, JsonValue],
) -> None:
    for relationship in await relationships_for_version(database, company_id, version_id):
        value = values.get(relationship.source_field_key)
        if value in (None, ""):
            continue
        try:
            target_id = UUID(str(value))
        except (TypeError, ValueError) as exc:
            raise MetadataServiceError(
                f"O relacionamento '{relationship.label}' exige UUID valido.", status_code=422
            ) from exc
        if (
            await get_record(database, company_id, relationship.target_definition_id, target_id)
            is None
        ):
            raise MetadataServiceError(
                f"O registro relacionado de '{relationship.label}' nao foi encontrado.",
                status_code=422,
            )


def field_permission_map(
    fields: Sequence[MetadataFieldDefinition], mode: Literal["read", "write"]
) -> dict[str, frozenset[str]]:
    key = f"{mode}_permission"
    result: dict[str, frozenset[str]] = {}
    for field in fields:
        permission = field.settings.get(key)
        result[field.key] = (
            frozenset({permission}) if isinstance(permission, str) and permission else frozenset()
        )
    return result


async def _load_published_schema(
    database: AsyncSession, company_id: UUID, definition_id: UUID
) -> tuple[MetadataEntityDefinition, MetadataEntityVersion, list[MetadataFieldDefinition]]:
    entity = await get_entity_definition(database, company_id, definition_id)
    version = await published_version(database, company_id, definition_id)
    if entity is None:
        raise MetadataServiceError("Definicao nao encontrada.", status_code=404)
    if version is None:
        raise MetadataServiceError(
            "A definicao ainda nao possui schema publicado.", status_code=409
        )
    fields = await list_version_fields(database, company_id, version.id)
    return entity, version, fields


async def _evaluate_record_policy(
    database: AsyncSession,
    context: RequestContext,
    *,
    correlation_id: UUID,
    action: PolicyAction,
    permission: str,
    fields: Sequence[MetadataFieldDefinition],
    mode: Literal["read", "write"],
    requested_fields: Sequence[str],
    record_id: UUID | None = None,
) -> PolicyDecision:
    decision = await evaluate_and_record_policy(
        database,
        PolicyRequest(
            subject=PolicySubject.from_request_context(context),
            resource=PolicyResource(
                company_id=context.company_id,
                resource_type="metadata_record",
                resource_id=str(record_id) if record_id else None,
                field_permissions=field_permission_map(fields, mode),
            ),
            action=action,
            required_permission=permission,
            requested_fields=tuple(requested_fields),
            correlation_id=correlation_id,
        ),
    )
    if not decision.allowed:
        await database.commit()
        raise MetadataServiceError("Operacao nao autorizada pela politica.", status_code=403)
    return decision


async def _ensure_unique_values(
    database: AsyncSession,
    company_id: UUID,
    definition_id: UUID,
    fields: Sequence[MetadataFieldDefinition],
    values: Mapping[str, JsonValue],
    *,
    excluding_record_id: UUID | None = None,
) -> None:
    for field in fields:
        if not field.unique_values or field.key not in values:
            continue
        if await unique_value_exists(
            database,
            company_id,
            definition_id,
            field.key,
            values[field.key],
            excluding_record_id=excluding_record_id,
        ):
            raise MetadataServiceError(
                f"Ja existe um registro com o mesmo valor em '{field.key}'.",
                status_code=409,
            )


def _response(
    record: MetadataRecord,
    *,
    allowed_fields: Sequence[str],
    denied_fields: Sequence[str],
) -> MetadataRecordResponse:
    allowed = set(allowed_fields)
    return MetadataRecordResponse(
        id=record.id,
        definition_id=record.definition_id,
        owner_user_id=record.owner_user_id,
        schema_version=record.schema_version,
        record_type_key=record.record_type_key,
        values={key: value for key, value in record.values.items() if key in allowed},
        masked_fields=sorted(denied_fields),
        record_version=record.record_version,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _combined_field_access(
    policy: PolicyDecision, security: MetadataAccessDecision
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    allowed = tuple(
        field for field in policy.allowed_fields if field in set(security.allowed_fields)
    )
    denied = tuple(sorted(set(policy.denied_fields) | set(security.denied_fields)))
    return allowed, denied


def _require_security_action(decision: MetadataAccessDecision) -> None:
    if not decision.allowed:
        raise MetadataServiceError("Operacao nao autorizada pela politica.", status_code=403)


def _revision(
    record: MetadataRecord, context: RequestContext, change_type: Literal["created", "updated"]
) -> MetadataRecordRevision:
    return MetadataRecordRevision(
        company_id=context.company_id,
        definition_id=record.definition_id,
        record_id=record.id,
        schema_version_id=record.schema_version_id,
        schema_version=record.schema_version,
        record_type_key=record.record_type_key,
        revision=record.record_version,
        change_type=change_type,
        values=dict(record.values),
        changed_by_user_id=context.user_id,
    )


def _emit_record_event(
    database: AsyncSession,
    *,
    event_type: str,
    context: RequestContext,
    correlation_id: UUID,
    definition_id: UUID,
    record_id: UUID,
    record_version: int,
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
                "definition_id": str(definition_id),
                "record_id": str(record_id),
                "record_version": record_version,
            },
        ),
    )


async def list_custom_records(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    correlation_id: UUID,
    *,
    page: int,
    page_size: int,
    view_key: str | None = None,
) -> MetadataRecordPage:
    _, version, fields = await _load_published_schema(database, context.company_id, definition_id)
    decision = await _evaluate_record_policy(
        database,
        context,
        correlation_id=correlation_id,
        action="list",
        permission="metadata.records.view",
        fields=fields,
        mode="read",
        requested_fields=[field.key for field in fields],
    )
    security = await evaluate_metadata_access(
        database,
        context,
        definition_id,
        action="view",
        field_keys=tuple(field.key for field in fields),
    )
    _require_security_action(security)
    allowed_fields, denied_fields = _combined_field_access(decision, security)
    stored_views = await views_for_version(database, context.company_id, version.id)
    selected_view: MetadataViewDefinition | None = None
    if view_key is not None:
        selected_view = next((item for item in stored_views if item.key == view_key), None)
        if selected_view is None:
            await database.commit()
            raise MetadataServiceError("Visualizacao nao encontrada.", status_code=404)
    elif stored_views:
        selected_view = next((item for item in stored_views if item.is_default), stored_views[0])

    filter_specs: list[MetadataRecordFilterSpec] = []
    sort_specs: list[MetadataRecordSortSpec] = []
    if selected_view is not None:
        view = MetadataViewInput(
            key=selected_view.key,
            label=selected_view.label,
            columns=selected_view.columns,
            filters=selected_view.filters,
            sorting=selected_view.sorting,
            is_default=selected_view.is_default,
        )
        field_by_key = {field.key: field for field in fields}
        errors = validate_view_contract(
            view, {key: field.data_type for key, field in field_by_key.items()}
        )
        if errors:
            await database.commit()
            raise MetadataServiceError(" ".join(errors), status_code=422)
        referenced_fields = {
            *(item.field_key for item in view.filters),
            *(item.field_key for item in view.sorting),
        }
        denied_references = sorted(referenced_fields - set(allowed_fields))
        if denied_references:
            await database.commit()
            raise MetadataServiceError(
                "A visualizacao usa campos que nao podem ser consultados.", status_code=403
            )
        for item in view.filters:
            field = field_by_key[item.field_key]
            value = item.value
            if item.operator not in VALUELESS_OPERATORS:
                try:
                    value = _normalize_value(field, item.value)
                except ValueError as exc:
                    await database.commit()
                    raise MetadataServiceError(str(exc), status_code=422) from exc
            filter_specs.append(
                MetadataRecordFilterSpec(
                    field_key=item.field_key,
                    data_type=cast(MetadataFieldType, field.data_type),
                    operator=item.operator,
                    value=value,
                )
            )
        sort_specs = [
            MetadataRecordSortSpec(
                field_key=item.field_key,
                data_type=cast(MetadataFieldType, field_by_key[item.field_key].data_type),
                direction=item.direction,
            )
            for item in view.sorting
        ]

    records, total = await list_records(
        database,
        context.company_id,
        definition_id,
        page=page,
        page_size=page_size,
        view_filters=filter_specs,
        view_sorting=sort_specs,
        access_scope=security.record_scope,
        actor_user_id=context.user_id,
        role_ids=context.role_ids,
    )
    await database.commit()
    return MetadataRecordPage(
        items=[
            _response(
                record,
                allowed_fields=allowed_fields,
                denied_fields=denied_fields,
            )
            for record in records
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total else 0,
    )


async def get_custom_record(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    record_id: UUID,
    correlation_id: UUID,
) -> MetadataRecordResponse:
    _, _, fields = await _load_published_schema(database, context.company_id, definition_id)
    record = await get_record(database, context.company_id, definition_id, record_id)
    if record is None:
        raise MetadataServiceError("Registro nao encontrado.", status_code=404)
    decision = await _evaluate_record_policy(
        database,
        context,
        correlation_id=correlation_id,
        action="view",
        permission="metadata.records.view",
        fields=fields,
        mode="read",
        requested_fields=[field.key for field in fields],
        record_id=record_id,
    )
    security = await evaluate_metadata_access(
        database,
        context,
        definition_id,
        action="view",
        field_keys=tuple(field.key for field in fields),
    )
    if not await record_is_accessible(database, context, record, security, action="view"):
        await database.commit()
        raise MetadataServiceError("Registro nao encontrado.", status_code=404)
    allowed_fields, denied_fields = _combined_field_access(decision, security)
    await database.commit()
    return _response(record, allowed_fields=allowed_fields, denied_fields=denied_fields)


async def create_custom_record(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    payload: MetadataRecordCreate,
    correlation_id: UUID,
) -> MetadataRecordResponse:
    _, version, fields = await _load_published_schema(database, context.company_id, definition_id)
    normalized, errors = await _prepare_record_values(
        database, context.company_id, version, fields, payload.values
    )
    if errors:
        raise MetadataServiceError(" ".join(errors), status_code=422)
    decision = await _evaluate_record_policy(
        database,
        context,
        correlation_id=correlation_id,
        action="create",
        permission="metadata.records.create",
        fields=fields,
        mode="write",
        requested_fields=tuple(payload.values),
    )
    security = await evaluate_metadata_access(
        database,
        context,
        definition_id,
        action="create",
        field_keys=tuple(payload.values),
    )
    _require_security_action(security)
    allowed_fields, denied_fields = _combined_field_access(decision, security)
    if denied_fields:
        await database.commit()
        raise MetadataServiceError(
            f"Sem permissao para gravar: {', '.join(denied_fields)}.", status_code=403
        )
    rule_errors = evaluate_record_validation_rules(
        await validation_rules_for_version(database, context.company_id, version.id),
        normalized,
    )
    if rule_errors:
        await database.commit()
        raise MetadataServiceError(" ".join(rule_errors), status_code=422)
    await _validate_relationship_values(database, context.company_id, version.id, normalized)
    record_type_key = await _resolve_record_type(
        database, context.company_id, version.id, payload.record_type_key
    )
    if payload.idempotency_key is not None:
        existing = await get_record_by_idempotency_key(
            database, context.company_id, definition_id, payload.idempotency_key
        )
        if existing is not None:
            if (
                existing.owner_user_id != context.user_id
                and not context.is_owner
                and not context.is_platform_admin
            ):
                await database.commit()
                raise MetadataServiceError("Conflito de idempotencia.", status_code=409)
            if existing.values != normalized:
                await database.commit()
                raise MetadataServiceError(
                    "A chave de idempotencia ja foi usada com outro conteudo.", status_code=409
                )
            await database.commit()
            return _response(existing, allowed_fields=allowed_fields, denied_fields=denied_fields)
    await _ensure_unique_values(database, context.company_id, definition_id, fields, normalized)
    record = MetadataRecord(
        company_id=context.company_id,
        definition_id=definition_id,
        schema_version_id=version.id,
        schema_version=version.version,
        record_type_key=record_type_key,
        values=normalized,
        record_version=1,
        idempotency_key=payload.idempotency_key,
        owner_user_id=context.user_id,
        created_by_user_id=context.user_id,
        updated_by_user_id=context.user_id,
    )
    database.add(record)
    await database.flush()
    database.add(_revision(record, context, "created"))
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.record.created",
        target_type="metadata_record",
        target_id=record.id,
        details={"definition_id": str(definition_id), "record_version": 1},
    )
    _emit_record_event(
        database,
        event_type="metadata.custom_record.created",
        context=context,
        correlation_id=correlation_id,
        definition_id=definition_id,
        record_id=record.id,
        record_version=1,
    )
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise MetadataServiceError(
            "Conflito ao criar o registro personalizado.", status_code=409
        ) from exc
    read_policy = await _evaluate_record_policy(
        database,
        context,
        correlation_id=correlation_id,
        action="view",
        permission="metadata.records.view",
        fields=fields,
        mode="read",
        requested_fields=tuple(normalized),
        record_id=record.id,
    )
    read_security = await evaluate_metadata_access(
        database,
        context,
        definition_id,
        action="view",
        field_keys=tuple(normalized),
    )
    response_allowed, response_denied = _combined_field_access(read_policy, read_security)
    await database.commit()
    return _response(
        record, allowed_fields=response_allowed, denied_fields=response_denied
    )


async def update_custom_record(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    record_id: UUID,
    payload: MetadataRecordUpdate,
    correlation_id: UUID,
) -> MetadataRecordResponse:
    _, version, fields = await _load_published_schema(database, context.company_id, definition_id)
    record = await get_record(database, context.company_id, definition_id, record_id)
    if record is None:
        raise MetadataServiceError("Registro nao encontrado.", status_code=404)
    if record.record_version != payload.expected_version:
        raise MetadataServiceError(
            "O registro foi alterado por outra operacao. Atualize os dados e tente novamente.",
            status_code=409,
        )
    decision = await _evaluate_record_policy(
        database,
        context,
        correlation_id=correlation_id,
        action="update",
        permission="metadata.records.update",
        fields=fields,
        mode="write",
        requested_fields=tuple(payload.values),
        record_id=record_id,
    )
    security = await evaluate_metadata_access(
        database,
        context,
        definition_id,
        action="update",
        field_keys=tuple(payload.values),
    )
    if not await record_is_accessible(database, context, record, security, action="update"):
        await database.commit()
        raise MetadataServiceError("Operacao nao autorizada pela politica.", status_code=403)
    _allowed_fields, denied_fields = _combined_field_access(decision, security)
    if denied_fields:
        await database.commit()
        raise MetadataServiceError(
            f"Sem permissao para gravar: {', '.join(denied_fields)}.", status_code=403
        )
    known_keys = {field.key for field in fields}
    combined = {key: value for key, value in record.values.items() if key in known_keys}
    combined.update(payload.values)
    normalized, errors = await _prepare_record_values(
        database, context.company_id, version, fields, combined
    )
    if errors:
        await database.commit()
        raise MetadataServiceError(" ".join(errors), status_code=422)
    rule_errors = evaluate_record_validation_rules(
        await validation_rules_for_version(database, context.company_id, version.id),
        normalized,
    )
    if rule_errors:
        await database.commit()
        raise MetadataServiceError(" ".join(rule_errors), status_code=422)
    await _validate_relationship_values(database, context.company_id, version.id, normalized)
    await _ensure_unique_values(
        database,
        context.company_id,
        definition_id,
        fields,
        normalized,
        excluding_record_id=record.id,
    )
    record.values = normalized
    record.schema_version_id = version.id
    record.schema_version = version.version
    record.record_type_key = await _resolve_record_type(
        database,
        context.company_id,
        version.id,
        payload.record_type_key or record.record_type_key,
    )
    record.record_version += 1
    record.updated_by_user_id = context.user_id
    record.updated_at = utc_now()
    database.add(_revision(record, context, "updated"))
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.record.updated",
        target_type="metadata_record",
        target_id=record.id,
        details={
            "definition_id": str(definition_id),
            "record_version": record.record_version,
            "changed_fields": sorted(payload.values),
        },
    )
    _emit_record_event(
        database,
        event_type="metadata.custom_record.updated",
        context=context,
        correlation_id=correlation_id,
        definition_id=definition_id,
        record_id=record.id,
        record_version=record.record_version,
    )
    readable_security = await evaluate_metadata_access(
        database,
        context,
        definition_id,
        action="view",
        field_keys=tuple(normalized),
    )
    response_allowed = tuple(
        field for field in normalized if field in set(readable_security.allowed_fields)
    )
    await database.commit()
    return _response(
        record,
        allowed_fields=response_allowed,
        denied_fields=tuple(sorted(set(normalized) - set(response_allowed))),
    )


async def delete_custom_record(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    record_id: UUID,
    expected_version: int,
    correlation_id: UUID,
) -> None:
    _, _, fields = await _load_published_schema(database, context.company_id, definition_id)
    record = await get_record(database, context.company_id, definition_id, record_id)
    if record is None:
        raise MetadataServiceError("Registro nao encontrado.", status_code=404)
    if record.record_version != expected_version:
        raise MetadataServiceError(
            "O registro foi alterado por outra operacao. Atualize os dados e tente novamente.",
            status_code=409,
        )
    for relationship, source_definition_id in await incoming_relationships_for_definition(
        database, context.company_id, definition_id
    ):
        if await relationship_reference_exists(
            database,
            context.company_id,
            source_definition_id,
            relationship.source_field_key,
            record_id,
        ):
            raise MetadataServiceError(
                f"O registro esta em uso pelo relacionamento '{relationship.label}'.",
                status_code=409,
            )
    await _evaluate_record_policy(
        database,
        context,
        correlation_id=correlation_id,
        action="delete",
        permission="metadata.records.delete",
        fields=fields,
        mode="write",
        requested_fields=(),
        record_id=record_id,
    )
    security = await evaluate_metadata_access(
        database,
        context,
        definition_id,
        action="delete",
        field_keys=(),
    )
    if not await record_is_accessible(database, context, record, security, action="delete"):
        await database.commit()
        raise MetadataServiceError("Operacao nao autorizada pela politica.", status_code=403)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.record.deleted",
        target_type="metadata_record",
        target_id=record.id,
        details={"definition_id": str(definition_id)},
    )
    _emit_record_event(
        database,
        event_type="metadata.custom_record.deleted",
        context=context,
        correlation_id=correlation_id,
        definition_id=definition_id,
        record_id=record.id,
        record_version=record.record_version,
    )
    await database.delete(record)
    await database.commit()
