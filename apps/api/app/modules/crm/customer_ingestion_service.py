from __future__ import annotations

import hashlib
import json
import re
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.customer_cdc_service import record_customer_change
from app.modules.crm.customer_ingestion_schemas import (
    CustomerDeadLetterResponse,
    CustomerIngestionJobCreate,
    CustomerIngestionJobResponse,
    CustomerIngestionRecordInput,
    CustomerIngestionRecordResponse,
    CustomerIngestionReprocess,
    CustomerQualityRuleSetCreate,
    CustomerQualityRuleSetResponse,
)

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _canonical_payload(record: CustomerIngestionRecordInput) -> str:
    return json.dumps(
        record.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def payload_fingerprint(record: CustomerIngestionRecordInput) -> str:
    return hashlib.sha256(_canonical_payload(record).encode()).hexdigest()


def masked_hint(value: str, kind: str) -> str:
    normalized = value.strip()
    if kind == "email" and "@" in normalized:
        local, domain = normalized.split("@", 1)
        return f"{local[:1]}***@{domain}"
    digits = "".join(character for character in normalized if character.isdigit())
    if kind == "phone":
        return f"***{digits[-4:]}" if digits else "***"
    return f"{normalized[:2]}***" if normalized else "***"


def validate_ingestion_record(
    record: CustomerIngestionRecordInput,
    rules: dict[str, Any],
) -> tuple[list[str], int]:
    errors: list[str] = []
    required = rules.get("required", ["external_id", "display_name"])
    for field_name in required:
        if field_name not in CustomerIngestionRecordInput.model_fields:
            continue
        value = getattr(record, field_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"{field_name}:required")
    if rules.get("email_format", True) and record.email:
        if _EMAIL_PATTERN.fullmatch(record.email.strip()) is None:
            errors.append("email:invalid_format")
    minimum_phone_digits = int(rules.get("phone_min_digits", 8))
    if record.phone:
        digits = "".join(character for character in record.phone if character.isdigit())
        if len(digits) < minimum_phone_digits:
            errors.append("phone:insufficient_digits")
    score = max(0, 100 - len(errors) * 35)
    if score < int(rules.get("minimum_score", 60)):
        errors.append("quality:below_minimum")
    return errors, score


async def _governance_event(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    event_type: str,
    subject_type: str,
    subject_id: UUID,
    payload: dict[str, Any],
) -> None:
    await database.execute(
        text(
            """
            INSERT INTO customer_data_governance_events (
                company_id, actor_user_id, event_type, subject_type, subject_id, payload
            ) VALUES (
                :company_id, :actor_user_id, :event_type, :subject_type, :subject_id,
                CAST(:payload AS jsonb)
            )
            """
        ),
        {
            "company_id": company_id,
            "actor_user_id": actor_user_id,
            "event_type": event_type,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "payload": json.dumps(payload),
        },
    )


def _quality_rule(row: Any) -> CustomerQualityRuleSetResponse:
    return CustomerQualityRuleSetResponse(
        id=row.id,
        version=row.version,
        name=row.name,
        status=row.status,
        rules=row.rules,
        created_at=row.created_at,
        published_at=row.published_at,
    )


async def list_quality_rule_sets(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> list[CustomerQualityRuleSetResponse]:
    rows = (
        await database.execute(
            text(
                """
                SELECT id, version, name, status, rules, created_at, published_at
                FROM customer_quality_rule_sets
                WHERE company_id = :company_id
                ORDER BY version DESC
                """
            ),
            {"company_id": company_id},
        )
    ).all()
    return [_quality_rule(row) for row in rows]


async def create_quality_rule_set(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    payload: CustomerQualityRuleSetCreate,
) -> CustomerQualityRuleSetResponse:
    row = (
        await database.execute(
            text(
                """
                INSERT INTO customer_quality_rule_sets (
                    company_id, version, name, status, rules, created_by_user_id
                )
                SELECT
                    :company_id, COALESCE(MAX(version), 0) + 1, :name,
                    'draft', CAST(:rules AS jsonb), :actor_user_id
                FROM customer_quality_rule_sets
                WHERE company_id = :company_id
                RETURNING id, version, name, status, rules, created_at, published_at
                """
            ),
            {
                "company_id": company_id,
                "actor_user_id": actor_user_id,
                "name": payload.name,
                "rules": json.dumps(payload.rules),
            },
        )
    ).one()
    response = _quality_rule(row)
    await _governance_event(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        event_type="customer.quality_rule.created",
        subject_type="quality_rule_set",
        subject_id=response.id,
        payload={"version": response.version},
    )
    return response


async def publish_quality_rule_set(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    rule_set_id: UUID,
) -> CustomerQualityRuleSetResponse:
    current = (
        await database.execute(
            text(
                """
                SELECT id, status
                FROM customer_quality_rule_sets
                WHERE company_id = :company_id AND id = :rule_set_id
                FOR UPDATE
                """
            ),
            {"company_id": company_id, "rule_set_id": rule_set_id},
        )
    ).one_or_none()
    if current is None:
        raise LookupError("Conjunto de regras de qualidade não encontrado.")
    if current.status != "draft":
        raise ValueError("Somente um conjunto em rascunho pode ser publicado.")
    await database.execute(
        text(
            """
            UPDATE customer_quality_rule_sets
            SET status = 'retired'
            WHERE company_id = :company_id AND status = 'published'
            """
        ),
        {"company_id": company_id},
    )
    row = (
        await database.execute(
            text(
                """
                UPDATE customer_quality_rule_sets
                SET status = 'published', published_at = now()
                WHERE company_id = :company_id AND id = :rule_set_id
                RETURNING id, version, name, status, rules, created_at, published_at
                """
            ),
            {"company_id": company_id, "rule_set_id": rule_set_id},
        )
    ).one()
    response = _quality_rule(row)
    await _governance_event(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        event_type="customer.quality_rule.published",
        subject_type="quality_rule_set",
        subject_id=response.id,
        payload={"version": response.version},
    )
    return response


async def _source(
    database: AsyncSession,
    *,
    company_id: UUID,
    code: str,
    name: str,
) -> Any:
    existing = (
        await database.execute(
            text(
                """
                SELECT id, code, name
                FROM customer_data_sources
                WHERE company_id = :company_id AND code = :code
                """
            ),
            {"company_id": company_id, "code": code},
        )
    ).one_or_none()
    if existing is not None:
        return existing
    return (
        await database.execute(
            text(
                """
                INSERT INTO customer_data_sources (
                    id, company_id, code, name, mode, status
                ) VALUES (
                    :id, :company_id, :code, :name, 'copied', 'active'
                )
                RETURNING id, code, name
                """
            ),
            {"id": uuid4(), "company_id": company_id, "code": code, "name": name},
        )
    ).one()


async def _published_quality_rule(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> Any:
    rule = (
        await database.execute(
            text(
                """
                SELECT id, version, rules
                FROM customer_quality_rule_sets
                WHERE company_id = :company_id AND status = 'published'
                ORDER BY version DESC
                LIMIT 1
                """
            ),
            {"company_id": company_id},
        )
    ).one_or_none()
    if rule is None:
        raise ValueError("Publique regras de qualidade antes de iniciar a ingestão.")
    return rule


async def _identity_profile(
    database: AsyncSession,
    *,
    company_id: UUID,
    source_id: UUID,
    external_id: str,
) -> UUID | None:
    value_hash = hashlib.sha256(external_id.strip().casefold().encode()).hexdigest()
    profile_id = await database.scalar(
        text(
            """
            SELECT profile_id
            FROM customer_identities
            WHERE company_id = :company_id
              AND data_source_id = :source_id
              AND identity_type = 'external_id'
              AND value_hash = :value_hash
            LIMIT 1
            """
        ),
        {
            "company_id": company_id,
            "source_id": source_id,
            "value_hash": value_hash,
        },
    )
    return cast(UUID | None, profile_id)


async def _insert_identity(
    database: AsyncSession,
    *,
    company_id: UUID,
    profile_id: UUID,
    source_id: UUID,
    identity_type: str,
    value: str,
) -> None:
    normalized = value.strip().casefold()
    value_hash = hashlib.sha256(normalized.encode()).hexdigest()
    await database.execute(
        text(
            """
            INSERT INTO customer_identities (
                id, company_id, profile_id, data_source_id, identity_type,
                value_hash, display_hint, verified
            )
            SELECT
                :id, :company_id, :profile_id, :source_id,
                CAST(:identity_type AS VARCHAR),
                CAST(:value_hash AS VARCHAR),
                CAST(:display_hint AS VARCHAR),
                false
            WHERE NOT EXISTS (
                SELECT 1
                FROM customer_identities
                WHERE company_id = :company_id
                  AND data_source_id = :source_id
                  AND identity_type = CAST(:identity_type AS VARCHAR)
                  AND value_hash = CAST(:value_hash AS VARCHAR)
            )
            """
        ),
        {
            "id": uuid4(),
            "company_id": company_id,
            "profile_id": profile_id,
            "source_id": source_id,
            "identity_type": identity_type,
            "value_hash": value_hash,
            "display_hint": masked_hint(value, identity_type),
        },
    )


async def _lineage(
    database: AsyncSession,
    *,
    company_id: UUID,
    profile_id: UUID,
    source_id: UUID,
    source_record_id: str,
    field_name: str,
    value: str,
    actor_user_id: UUID,
) -> None:
    await database.execute(
        text(
            """
            UPDATE customer_field_lineage
            SET selected = false
            WHERE company_id = :company_id
              AND profile_id = :profile_id
              AND field_name = :field_name
            """
        ),
        {
            "company_id": company_id,
            "profile_id": profile_id,
            "field_name": field_name,
        },
    )
    await database.execute(
        text(
            """
            INSERT INTO customer_field_lineage (
                company_id, profile_id, field_name, value_fingerprint,
                source_id, source_record_id, classification, selected,
                recorded_by_user_id
            ) VALUES (
                :company_id, :profile_id, :field_name, :value_fingerprint,
                :source_id, :source_record_id, 'confidential', true,
                :actor_user_id
            )
            """
        ),
        {
            "company_id": company_id,
            "profile_id": profile_id,
            "field_name": field_name,
            "value_fingerprint": hashlib.sha256(value.encode()).hexdigest(),
            "source_id": source_id,
            "source_record_id": source_record_id,
            "actor_user_id": actor_user_id,
        },
    )


async def _consolidate_record(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    source_id: UUID,
    record: CustomerIngestionRecordInput,
    quality_score: int,
) -> UUID:
    if record.external_id is None or record.display_name is None:
        raise ValueError("Registro sem identidade externa ou nome.")
    profile_id = await _identity_profile(
        database,
        company_id=company_id,
        source_id=source_id,
        external_id=record.external_id,
    )
    if profile_id is None:
        profile_id = uuid4()
        await database.execute(
            text(
                """
                INSERT INTO customer_profiles (
                    id, company_id, display_name, profile_type, lifecycle_status,
                    quality_score, created_by_user_id, status
                ) VALUES (
                    :id, :company_id, :display_name, 'person', 'lead',
                    :quality_score, :actor_user_id, 'active'
                )
                """
            ),
            {
                "id": profile_id,
                "company_id": company_id,
                "display_name": record.display_name.strip(),
                "quality_score": quality_score,
                "actor_user_id": actor_user_id,
            },
        )
    else:
        await database.execute(
            text(
                """
                UPDATE customer_profiles
                SET display_name = :display_name,
                    quality_score = :quality_score,
                    updated_at = now()
                WHERE company_id = :company_id AND id = :profile_id
                """
            ),
            {
                "company_id": company_id,
                "profile_id": profile_id,
                "display_name": record.display_name.strip(),
                "quality_score": quality_score,
            },
        )

    identities = (
        ("external_id", record.external_id),
        ("email", record.email),
        ("phone", record.phone),
    )
    for identity_type, value in identities:
        if value:
            await _insert_identity(
                database,
                company_id=company_id,
                profile_id=profile_id,
                source_id=source_id,
                identity_type=identity_type,
                value=value,
            )
    for field_name, value in (
        ("display_name", record.display_name),
        ("email", record.email),
        ("phone", record.phone),
    ):
        if value:
            await _lineage(
                database,
                company_id=company_id,
                profile_id=profile_id,
                source_id=source_id,
                source_record_id=record.source_record_id,
                field_name=field_name,
                value=value,
                actor_user_id=actor_user_id,
            )
    return profile_id


def _record_response(row: Any) -> CustomerIngestionRecordResponse:
    return CustomerIngestionRecordResponse(
        id=row.id,
        source_record_id=row.source_record_id,
        payload_fingerprint=f"{row.payload_hash[:12]}…",
        status=row.status,
        error_code=row.error_code,
        errors=list(row.errors),
        profile_id=row.profile_id,
        attempts=row.attempts,
        processed_at=row.processed_at,
    )


async def _job_response(
    database: AsyncSession,
    *,
    company_id: UUID,
    job_id: UUID,
) -> CustomerIngestionJobResponse:
    job = (
        await database.execute(
            text(
                """
                SELECT
                    job.id, source.code AS source_code, source.name AS source_name,
                    rule.version AS quality_rule_version, job.mode, job.status,
                    job.idempotency_key, job.cursor, job.total_records,
                    job.accepted_records, job.rejected_records, job.created_at,
                    job.completed_at
                FROM customer_ingestion_jobs AS job
                JOIN customer_data_sources AS source
                  ON source.id = job.source_id AND source.company_id = job.company_id
                JOIN customer_quality_rule_sets AS rule
                  ON rule.id = job.quality_rule_set_id
                 AND rule.company_id = job.company_id
                WHERE job.company_id = :company_id AND job.id = :job_id
                """
            ),
            {"company_id": company_id, "job_id": job_id},
        )
    ).one()
    records = (
        await database.execute(
            text(
                """
                SELECT id, source_record_id, payload_hash, status, error_code,
                       errors, profile_id, attempts, processed_at
                FROM customer_ingestion_records
                WHERE company_id = :company_id AND job_id = :job_id
                ORDER BY created_at
                """
            ),
            {"company_id": company_id, "job_id": job_id},
        )
    ).all()
    return CustomerIngestionJobResponse(
        id=job.id,
        source_code=job.source_code,
        source_name=job.source_name,
        quality_rule_version=job.quality_rule_version,
        mode=job.mode,
        status=job.status,
        idempotency_key=job.idempotency_key,
        cursor=job.cursor,
        total_records=job.total_records,
        accepted_records=job.accepted_records,
        rejected_records=job.rejected_records,
        created_at=job.created_at,
        completed_at=job.completed_at,
        records=[_record_response(row) for row in records],
    )


async def ingest_customer_records(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    payload: CustomerIngestionJobCreate,
) -> CustomerIngestionJobResponse:
    existing = (
        await database.execute(
            text(
                """
                SELECT id
                FROM customer_ingestion_jobs
                WHERE company_id = :company_id AND idempotency_key = :idempotency_key
                """
            ),
            {"company_id": company_id, "idempotency_key": payload.idempotency_key},
        )
    ).one_or_none()
    if existing is not None:
        return await _job_response(database, company_id=company_id, job_id=existing.id)

    rule = await _published_quality_rule(database, company_id=company_id)
    source = await _source(
        database,
        company_id=company_id,
        code=payload.source_code,
        name=payload.source_name,
    )
    job_id = uuid4()
    await database.execute(
        text(
            """
            INSERT INTO customer_ingestion_jobs (
                id, company_id, source_id, quality_rule_set_id, mode, status,
                idempotency_key, cursor, total_records, requested_by_user_id,
                started_at
            ) VALUES (
                :id, :company_id, :source_id, :rule_id, :mode, 'running',
                :idempotency_key, :cursor, :total_records, :actor_user_id, now()
            )
            """
        ),
        {
            "id": job_id,
            "company_id": company_id,
            "source_id": source.id,
            "rule_id": rule.id,
            "mode": payload.mode,
            "idempotency_key": payload.idempotency_key,
            "cursor": payload.cursor,
            "total_records": len(payload.records),
            "actor_user_id": actor_user_id,
        },
    )
    accepted = 0
    rejected = 0
    for record in payload.records:
        errors, quality_score = validate_ingestion_record(record, rule.rules)
        profile_id: UUID | None = None
        record_status = "rejected" if errors else "accepted"
        if not errors:
            profile_id = await _consolidate_record(
                database,
                company_id=company_id,
                actor_user_id=actor_user_id,
                source_id=source.id,
                record=record,
                quality_score=quality_score,
            )
            await record_customer_change(
                database,
                company_id=company_id,
                actor_user_id=actor_user_id,
                profile_id=profile_id,
                source_id=source.id,
                ingestion_job_id=job_id,
                operation="upserted",
                record=record.model_dump(mode="json"),
            )
            accepted += 1
        else:
            rejected += 1
        await database.execute(
            text(
                """
                INSERT INTO customer_ingestion_records (
                    company_id, job_id, source_record_id, payload_hash, status,
                    error_code, errors, profile_id, attempts, processed_at
                ) VALUES (
                    :company_id, :job_id, :source_record_id, :payload_hash, :status,
                    :error_code, CAST(:errors AS jsonb), :profile_id, 1, now()
                )
                """
            ),
            {
                "company_id": company_id,
                "job_id": job_id,
                "source_record_id": record.source_record_id,
                "payload_hash": payload_fingerprint(record),
                "status": record_status,
                "error_code": "quality_validation_failed" if errors else None,
                "errors": json.dumps(errors),
                "profile_id": profile_id,
            },
        )
    job_status = "completed" if rejected == 0 else "failed" if accepted == 0 else "partial"
    await database.execute(
        text(
            """
            UPDATE customer_ingestion_jobs
            SET status = :status,
                accepted_records = :accepted,
                rejected_records = :rejected,
                completed_at = now()
            WHERE company_id = :company_id AND id = :job_id
            """
        ),
        {
            "company_id": company_id,
            "job_id": job_id,
            "status": job_status,
            "accepted": accepted,
            "rejected": rejected,
        },
    )
    await _governance_event(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        event_type="customer.ingestion.completed",
        subject_type="ingestion_job",
        subject_id=job_id,
        payload={
            "mode": payload.mode,
            "total": len(payload.records),
            "accepted": accepted,
            "rejected": rejected,
        },
    )
    return await _job_response(database, company_id=company_id, job_id=job_id)


async def list_ingestion_jobs(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> list[CustomerIngestionJobResponse]:
    ids = (
        await database.execute(
            text(
                """
                SELECT id
                FROM customer_ingestion_jobs
                WHERE company_id = :company_id
                ORDER BY created_at DESC
                LIMIT 50
                """
            ),
            {"company_id": company_id},
        )
    ).scalars()
    return [await _job_response(database, company_id=company_id, job_id=job_id) for job_id in ids]


async def list_dead_letters(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> list[CustomerDeadLetterResponse]:
    rows = (
        await database.execute(
            text(
                """
                SELECT
                    record.id, record.job_id, source.code AS source_code,
                    record.source_record_id, record.payload_hash, record.error_code,
                    record.errors, record.attempts, record.created_at, record.processed_at
                FROM customer_ingestion_records AS record
                JOIN customer_ingestion_jobs AS job
                  ON job.id = record.job_id AND job.company_id = record.company_id
                JOIN customer_data_sources AS source
                  ON source.id = job.source_id AND source.company_id = job.company_id
                WHERE record.company_id = :company_id
                  AND record.status IN ('rejected', 'dead_letter')
                ORDER BY record.created_at DESC
                LIMIT 200
                """
            ),
            {"company_id": company_id},
        )
    ).all()
    return [
        CustomerDeadLetterResponse(
            id=row.id,
            job_id=row.job_id,
            source_code=row.source_code,
            source_record_id=row.source_record_id,
            payload_fingerprint=f"{row.payload_hash[:12]}…",
            error_code=row.error_code,
            errors=list(row.errors),
            attempts=row.attempts,
            created_at=row.created_at,
            processed_at=row.processed_at,
        )
        for row in rows
    ]


async def reprocess_dead_letter(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    record_id: UUID,
    payload: CustomerIngestionReprocess,
) -> CustomerIngestionRecordResponse:
    stored = (
        await database.execute(
            text(
                """
                SELECT
                    record.id, record.job_id, record.source_record_id, record.status,
                    record.attempts, job.source_id, job.quality_rule_set_id
                FROM customer_ingestion_records AS record
                JOIN customer_ingestion_jobs AS job
                  ON job.id = record.job_id AND job.company_id = record.company_id
                WHERE record.company_id = :company_id AND record.id = :record_id
                FOR UPDATE
                """
            ),
            {"company_id": company_id, "record_id": record_id},
        )
    ).one_or_none()
    if stored is None:
        raise LookupError("Registro da fila de erros não encontrado.")
    if stored.status not in ("rejected", "dead_letter"):
        raise ValueError("Somente registros rejeitados podem ser reprocessados.")
    if payload.record.source_record_id != stored.source_record_id:
        raise ValueError("O identificador de origem não pode ser alterado.")
    rule = (
        await database.execute(
            text(
                """
                SELECT rules
                FROM customer_quality_rule_sets
                WHERE company_id = :company_id AND id = :rule_set_id
                """
            ),
            {"company_id": company_id, "rule_set_id": stored.quality_rule_set_id},
        )
    ).one()
    errors, quality_score = validate_ingestion_record(payload.record, rule.rules)
    profile_id: UUID | None = None
    next_status = "dead_letter" if errors else "accepted"
    if not errors:
        profile_id = await _consolidate_record(
            database,
            company_id=company_id,
            actor_user_id=actor_user_id,
            source_id=stored.source_id,
            record=payload.record,
            quality_score=quality_score,
        )
        await record_customer_change(
            database,
            company_id=company_id,
            actor_user_id=actor_user_id,
            profile_id=profile_id,
            source_id=stored.source_id,
            ingestion_job_id=stored.job_id,
            operation="upserted",
            record=payload.record.model_dump(mode="json"),
        )
    row = (
        await database.execute(
            text(
                """
                UPDATE customer_ingestion_records
                SET payload_hash = :payload_hash,
                    status = :status,
                    error_code = :error_code,
                    errors = CAST(:errors AS jsonb),
                    profile_id = :profile_id,
                    attempts = attempts + 1,
                    processed_at = now()
                WHERE company_id = :company_id AND id = :record_id
                RETURNING id, source_record_id, payload_hash, status, error_code,
                          errors, profile_id, attempts, processed_at
                """
            ),
            {
                "company_id": company_id,
                "record_id": record_id,
                "payload_hash": payload_fingerprint(payload.record),
                "status": next_status,
                "error_code": "quality_validation_failed" if errors else None,
                "errors": json.dumps(errors),
                "profile_id": profile_id,
            },
        )
    ).one()
    await database.execute(
        text(
            """
            UPDATE customer_ingestion_jobs AS job
            SET accepted_records = summary.accepted,
                rejected_records = summary.rejected,
                status = CASE
                    WHEN summary.rejected = 0 THEN 'completed'
                    WHEN summary.accepted = 0 THEN 'failed'
                    ELSE 'partial'
                END
            FROM (
                SELECT
                    COUNT(*) FILTER (WHERE status = 'accepted') AS accepted,
                    COUNT(*) FILTER (WHERE status IN ('rejected', 'dead_letter')) AS rejected
                FROM customer_ingestion_records
                WHERE company_id = :company_id AND job_id = :job_id
            ) AS summary
            WHERE job.company_id = :company_id AND job.id = :job_id
            """
        ),
        {"company_id": company_id, "job_id": stored.job_id},
    )
    await _governance_event(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        event_type="customer.ingestion.reprocessed",
        subject_type="ingestion_record",
        subject_id=record_id,
        payload={
            "status": next_status,
            "reason": payload.reason,
            "attempt": stored.attempts + 1,
        },
    )
    return _record_response(row)
