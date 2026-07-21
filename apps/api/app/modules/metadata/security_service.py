from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy import RequestContext
from app.modules.authorization.models import Role
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.metadata.models import (
    MetadataEntityAccessRule,
    MetadataEntityVersion,
    MetadataFieldAccessRule,
    MetadataRecord,
    MetadataRecordShare,
)
from app.modules.metadata.repository import get_entity_definition, list_version_fields
from app.modules.metadata.security_schemas import (
    MetadataEntityAccessRuleResponse,
    MetadataFieldAccessRuleResponse,
    MetadataRecordShareCreate,
    MetadataRecordShareResponse,
    MetadataSecurityConfigurationResponse,
    MetadataSecurityConfigurationUpdate,
)
from app.modules.users.models import CompanyUser

MetadataSecurityAction = Literal["view", "create", "update", "delete"]


class MetadataSecurityError(ValueError):
    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class MetadataAccessDecision:
    allowed: bool
    configured: bool
    record_scope: Literal["all", "owned", "owned_shared"]
    allowed_fields: tuple[str, ...]
    denied_fields: tuple[str, ...]


def _subject_matches(subject_type: str, subject_id: UUID, context: RequestContext) -> bool:
    if subject_type == "user":
        return subject_id == context.user_id
    return subject_type == "role" and subject_id in context.role_ids


def _entity_response(rule: MetadataEntityAccessRule) -> MetadataEntityAccessRuleResponse:
    return MetadataEntityAccessRuleResponse(
        id=rule.id,
        subject_type=rule.subject_type,
        subject_id=rule.subject_id,
        can_view=rule.can_view,
        can_create=rule.can_create,
        can_update=rule.can_update,
        can_delete=rule.can_delete,
        can_export=rule.can_export,
        record_scope=rule.record_scope,
    )


def _field_response(rule: MetadataFieldAccessRule) -> MetadataFieldAccessRuleResponse:
    return MetadataFieldAccessRuleResponse(
        id=rule.id,
        field_key=rule.field_key,
        subject_type=rule.subject_type,
        subject_id=rule.subject_id,
        can_view=rule.can_view,
        can_edit=rule.can_edit,
    )


def _share_response(share: MetadataRecordShare) -> MetadataRecordShareResponse:
    return MetadataRecordShareResponse(
        id=share.id,
        record_id=share.record_id,
        subject_type=share.subject_type,
        subject_id=share.subject_id,
        can_view=share.can_view,
        can_edit=share.can_edit,
        created_at=share.created_at,
        updated_at=share.updated_at,
    )


async def _require_definition(
    database: AsyncSession, context: RequestContext, definition_id: UUID
) -> None:
    if await get_entity_definition(database, context.company_id, definition_id) is None:
        raise MetadataSecurityError("Definicao nao encontrada.", status_code=404)


async def _validate_subject(
    database: AsyncSession,
    context: RequestContext,
    subject_type: str,
    subject_id: UUID,
) -> None:
    if subject_type == "user":
        found = await database.scalar(
            select(CompanyUser.user_id).where(
                CompanyUser.company_id == context.company_id,
                CompanyUser.user_id == subject_id,
                CompanyUser.status == "active",
            )
        )
    else:
        found = await database.scalar(
            select(Role.id).where(Role.company_id == context.company_id, Role.id == subject_id)
        )
    if found is None:
        raise MetadataSecurityError(
            "Usuario ou papel nao pertence a empresa atual.", status_code=422
        )


def _emit_security_event(
    database: AsyncSession,
    *,
    event_type: str,
    context: RequestContext,
    correlation_id: UUID,
    definition_id: UUID,
    payload: dict[str, object],
) -> None:
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=event_type,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            correlation_id=correlation_id,
            classification="internal",
            payload={"definition_id": str(definition_id), **payload},
        ),
    )


async def get_security_configuration(
    database: AsyncSession, context: RequestContext, definition_id: UUID
) -> MetadataSecurityConfigurationResponse:
    await _require_definition(database, context, definition_id)
    entity_rules = list(
        await database.scalars(
            select(MetadataEntityAccessRule)
            .where(
                MetadataEntityAccessRule.company_id == context.company_id,
                MetadataEntityAccessRule.definition_id == definition_id,
            )
            .order_by(
                MetadataEntityAccessRule.subject_type, MetadataEntityAccessRule.subject_id
            )
        )
    )
    field_rules = list(
        await database.scalars(
            select(MetadataFieldAccessRule)
            .where(
                MetadataFieldAccessRule.company_id == context.company_id,
                MetadataFieldAccessRule.definition_id == definition_id,
            )
            .order_by(
                MetadataFieldAccessRule.field_key,
                MetadataFieldAccessRule.subject_type,
                MetadataFieldAccessRule.subject_id,
            )
        )
    )
    return MetadataSecurityConfigurationResponse(
        definition_id=definition_id,
        configured=bool(entity_rules or field_rules),
        entity_rules=[_entity_response(item) for item in entity_rules],
        field_rules=[_field_response(item) for item in field_rules],
    )


async def replace_security_configuration(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    payload: MetadataSecurityConfigurationUpdate,
    correlation_id: UUID,
) -> MetadataSecurityConfigurationResponse:
    entity = await get_entity_definition(database, context.company_id, definition_id)
    if entity is None:
        raise MetadataSecurityError("Definicao nao encontrada.", status_code=404)
    version = await database.scalar(
        select(MetadataEntityVersion).where(
            MetadataEntityVersion.company_id == context.company_id,
            MetadataEntityVersion.definition_id == definition_id,
            MetadataEntityVersion.version == entity.current_version,
        )
    )
    if version is None:
        raise MetadataSecurityError("Versao da definicao nao encontrada.", status_code=409)
    valid_fields = {
        field.key for field in await list_version_fields(database, context.company_id, version.id)
    }
    unknown_fields = sorted({item.field_key for item in payload.field_rules} - valid_fields)
    if unknown_fields:
        raise MetadataSecurityError(
            f"Campos inexistentes na versao atual: {', '.join(unknown_fields)}.",
            status_code=422,
        )
    subjects: set[tuple[str, UUID]] = set()
    subjects.update((item.subject_type, item.subject_id) for item in payload.entity_rules)
    subjects.update((item.subject_type, item.subject_id) for item in payload.field_rules)
    for subject_type, subject_id in subjects:
        await _validate_subject(database, context, subject_type, subject_id)

    await database.execute(
        delete(MetadataFieldAccessRule).where(
            MetadataFieldAccessRule.company_id == context.company_id,
            MetadataFieldAccessRule.definition_id == definition_id,
        )
    )
    await database.execute(
        delete(MetadataEntityAccessRule).where(
            MetadataEntityAccessRule.company_id == context.company_id,
            MetadataEntityAccessRule.definition_id == definition_id,
        )
    )
    database.add_all(
        [
            MetadataEntityAccessRule(
                company_id=context.company_id,
                definition_id=definition_id,
                created_by_user_id=context.user_id,
                **item.model_dump(),
            )
            for item in payload.entity_rules
        ]
        + [
            MetadataFieldAccessRule(
                company_id=context.company_id,
                definition_id=definition_id,
                created_by_user_id=context.user_id,
                **item.model_dump(),
            )
            for item in payload.field_rules
        ]
    )
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.security.updated",
        target_type="metadata_entity_definition",
        target_id=definition_id,
        details={
            "entity_rule_count": len(payload.entity_rules),
            "field_rule_count": len(payload.field_rules),
        },
    )
    _emit_security_event(
        database,
        event_type="metadata.security.updated",
        context=context,
        correlation_id=correlation_id,
        definition_id=definition_id,
        payload={
            "entity_rule_count": len(payload.entity_rules),
            "field_rule_count": len(payload.field_rules),
        },
    )
    await database.commit()
    return await get_security_configuration(database, context, definition_id)


async def evaluate_metadata_access(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    *,
    action: MetadataSecurityAction,
    field_keys: tuple[str, ...],
) -> MetadataAccessDecision:
    if context.is_owner or context.is_platform_admin:
        return MetadataAccessDecision(True, False, "all", field_keys, ())

    entity_rules = list(
        await database.scalars(
            select(MetadataEntityAccessRule).where(
                MetadataEntityAccessRule.company_id == context.company_id,
                MetadataEntityAccessRule.definition_id == definition_id,
            )
        )
    )
    if not entity_rules:
        return MetadataAccessDecision(True, False, "all", field_keys, ())
    matching = [
        item
        for item in entity_rules
        if _subject_matches(item.subject_type, item.subject_id, context)
    ]
    user_rules = [
        item
        for item in matching
        if item.subject_type == "user" and item.subject_id == context.user_id
    ]
    effective = user_rules or matching
    permission_attribute = {
        "view": "can_view",
        "create": "can_create",
        "update": "can_update",
        "delete": "can_delete",
    }[action]
    allowed = any(bool(getattr(item, permission_attribute)) for item in effective)
    scope_rank = {"owned": 0, "owned_shared": 1, "all": 2}
    record_scope = max(
        (item.record_scope for item in effective),
        key=lambda value: scope_rank[value],
        default="owned",
    )

    field_rules = list(
        await database.scalars(
            select(MetadataFieldAccessRule).where(
                MetadataFieldAccessRule.company_id == context.company_id,
                MetadataFieldAccessRule.definition_id == definition_id,
                MetadataFieldAccessRule.field_key.in_(field_keys),
            )
        )
    )
    allowed_fields: list[str] = []
    denied_fields: list[str] = []
    for field_key in field_keys:
        rules = [item for item in field_rules if item.field_key == field_key]
        if not rules:
            allowed_fields.append(field_key)
            continue
        matching_fields = [
            item for item in rules if _subject_matches(item.subject_type, item.subject_id, context)
        ]
        user_fields = [
            item
            for item in matching_fields
            if item.subject_type == "user" and item.subject_id == context.user_id
        ]
        effective_fields = user_fields or matching_fields
        field_allowed = any(
            item.can_view if action == "view" else item.can_edit for item in effective_fields
        )
        (allowed_fields if field_allowed else denied_fields).append(field_key)
    return MetadataAccessDecision(
        allowed=allowed,
        configured=True,
        record_scope=record_scope,  # type: ignore[arg-type]
        allowed_fields=tuple(allowed_fields),
        denied_fields=tuple(denied_fields),
    )


async def record_is_accessible(
    database: AsyncSession,
    context: RequestContext,
    record: MetadataRecord,
    decision: MetadataAccessDecision,
    *,
    action: MetadataSecurityAction,
) -> bool:
    if not decision.allowed:
        return False
    if decision.record_scope == "all" or record.owner_user_id == context.user_id:
        return True
    if decision.record_scope == "owned" or action == "delete":
        return False
    permission = (
        MetadataRecordShare.can_edit if action == "update" else MetadataRecordShare.can_view
    )
    matching_share = await database.scalar(
        select(MetadataRecordShare.id).where(
            MetadataRecordShare.company_id == context.company_id,
            MetadataRecordShare.definition_id == record.definition_id,
            MetadataRecordShare.record_id == record.id,
            permission.is_(True),
            (
                (MetadataRecordShare.subject_type == "user")
                & (MetadataRecordShare.subject_id == context.user_id)
            )
            | (
                (MetadataRecordShare.subject_type == "role")
                & (MetadataRecordShare.subject_id.in_(context.role_ids or (UUID(int=0),)))
            ),
        )
    )
    return matching_share is not None


async def list_record_shares(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    record_id: UUID,
) -> list[MetadataRecordShareResponse]:
    record = await database.scalar(
        select(MetadataRecord).where(
            MetadataRecord.company_id == context.company_id,
            MetadataRecord.definition_id == definition_id,
            MetadataRecord.id == record_id,
            MetadataRecord.deleted_at.is_(None),
        )
    )
    if record is None:
        raise MetadataSecurityError("Registro nao encontrado.", status_code=404)
    shares = list(
        await database.scalars(
            select(MetadataRecordShare)
            .where(
                MetadataRecordShare.company_id == context.company_id,
                MetadataRecordShare.definition_id == definition_id,
                MetadataRecordShare.record_id == record_id,
            )
            .order_by(MetadataRecordShare.created_at)
        )
    )
    return [_share_response(item) for item in shares]


async def upsert_record_share(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    record_id: UUID,
    payload: MetadataRecordShareCreate,
    correlation_id: UUID,
) -> MetadataRecordShareResponse:
    await _validate_subject(database, context, payload.subject_type, payload.subject_id)
    record = await database.scalar(
        select(MetadataRecord).where(
            MetadataRecord.company_id == context.company_id,
            MetadataRecord.definition_id == definition_id,
            MetadataRecord.id == record_id,
            MetadataRecord.deleted_at.is_(None),
        )
    )
    if record is None:
        raise MetadataSecurityError("Registro nao encontrado.", status_code=404)
    share = await database.scalar(
        select(MetadataRecordShare).where(
            MetadataRecordShare.company_id == context.company_id,
            MetadataRecordShare.record_id == record_id,
            MetadataRecordShare.subject_type == payload.subject_type,
            MetadataRecordShare.subject_id == payload.subject_id,
        )
    )
    if share is None:
        share = MetadataRecordShare(
            company_id=context.company_id,
            definition_id=definition_id,
            record_id=record_id,
            subject_type=payload.subject_type,
            subject_id=payload.subject_id,
            created_by_user_id=context.user_id,
        )
        database.add(share)
    share.can_view = payload.can_view
    share.can_edit = payload.can_edit
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.record.shared",
        target_type="metadata_record",
        target_id=record_id,
        details={
            "definition_id": str(definition_id),
            "subject_type": payload.subject_type,
            "subject_id": str(payload.subject_id),
            "can_edit": payload.can_edit,
        },
    )
    _emit_security_event(
        database,
        event_type="metadata.record.shared",
        context=context,
        correlation_id=correlation_id,
        definition_id=definition_id,
        payload={"record_id": str(record_id), "can_edit": payload.can_edit},
    )
    await database.commit()
    return _share_response(share)


async def delete_record_share(
    database: AsyncSession,
    context: RequestContext,
    definition_id: UUID,
    record_id: UUID,
    share_id: UUID,
    correlation_id: UUID,
) -> None:
    share = await database.scalar(
        select(MetadataRecordShare).where(
            MetadataRecordShare.id == share_id,
            MetadataRecordShare.company_id == context.company_id,
            MetadataRecordShare.definition_id == definition_id,
            MetadataRecordShare.record_id == record_id,
        )
    )
    if share is None:
        raise MetadataSecurityError("Compartilhamento nao encontrado.", status_code=404)
    await database.delete(share)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.record.share_revoked",
        target_type="metadata_record",
        target_id=record_id,
        details={"definition_id": str(definition_id), "share_id": str(share_id)},
    )
    _emit_security_event(
        database,
        event_type="metadata.record.share_revoked",
        context=context,
        correlation_id=correlation_id,
        definition_id=definition_id,
        payload={"record_id": str(record_id), "share_id": str(share_id)},
    )
    await database.commit()
