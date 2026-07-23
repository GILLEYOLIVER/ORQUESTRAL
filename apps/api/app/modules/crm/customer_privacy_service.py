from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.customer_privacy_schemas import (
    CustomerPrivacyDecisionRequest,
    CustomerPrivacyLegalHoldRequest,
    CustomerPrivacyRequestCreate,
    CustomerPrivacyRequestResponse,
    CustomerPrivacySummaryResponse,
)


def privacy_reference_fingerprint(company_id: UUID, reference: str) -> str:
    normalized = " ".join(reference.strip().lower().split())
    return hashlib.sha256(f"{company_id}:{normalized}".encode()).hexdigest()


def _request_response(row: RowMapping) -> CustomerPrivacyRequestResponse:
    return CustomerPrivacyRequestResponse(
        id=row["id"],
        profile_id=row["profile_id"],
        request_type=row["request_type"],
        status=row["status"],
        reason_code=row["reason_code"],
        scope=list(row["scope"]),
        legal_hold=row["legal_hold"],
        legal_hold_reason=row["legal_hold_reason"],
        due_at=row["due_at"],
        requested_at=row["requested_at"],
        verified_at=row["verified_at"],
        decided_at=row["decided_at"],
        completed_at=row["completed_at"],
        result_counts=dict(row["result_counts"]),
    )


async def _privacy_event(
    database: AsyncSession,
    *,
    company_id: UUID,
    request_id: UUID,
    actor_user_id: UUID,
    event_type: str,
    previous_status: str | None,
    new_status: str,
) -> None:
    await database.execute(
        text(
            """
            INSERT INTO customer_privacy_request_events (
                id,
                company_id,
                request_id,
                event_type,
                previous_status,
                new_status,
                actor_user_id,
                occurred_at
            )
            VALUES (
                :id,
                :company_id,
                :request_id,
                :event_type,
                :previous_status,
                :new_status,
                :actor_user_id,
                now()
            )
            """
        ),
        {
            "id": uuid4(),
            "company_id": company_id,
            "request_id": request_id,
            "event_type": event_type,
            "previous_status": previous_status,
            "new_status": new_status,
            "actor_user_id": actor_user_id,
        },
    )


async def list_customer_privacy_requests(
    database: AsyncSession,
    *,
    company_id: UUID,
    limit: int = 100,
) -> list[CustomerPrivacyRequestResponse]:
    rows = (
        (
            await database.execute(
                text(
                    """
                    SELECT *
                    FROM customer_privacy_requests
                    WHERE company_id = :company_id
                    ORDER BY requested_at DESC
                    LIMIT :limit
                    """
                ),
                {"company_id": company_id, "limit": limit},
            )
        )
        .mappings()
        .all()
    )
    return [_request_response(row) for row in rows]


async def create_customer_privacy_request(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    payload: CustomerPrivacyRequestCreate,
) -> CustomerPrivacyRequestResponse:
    profile = (
        await database.execute(
            text(
                """
                SELECT id
                FROM customer_profiles
                WHERE id = :profile_id
                  AND company_id = :company_id
                  AND status = 'active'
                """
            ),
            {"company_id": company_id, "profile_id": payload.profile_id},
        )
    ).scalar_one_or_none()
    if profile is None:
        raise LookupError("Perfil de cliente ativo nao encontrado.")

    request_id = uuid4()
    requested_at = datetime.now(UTC)
    row = (
        (
            await database.execute(
                text(
                    """
                    INSERT INTO customer_privacy_requests (
                        id,
                        company_id,
                        profile_id,
                        profile_reference_hash,
                        request_type,
                        status,
                        reason_code,
                        request_reference_hash,
                        scope,
                        legal_hold,
                        due_at,
                        requested_by_user_id,
                        requested_at,
                        result_counts
                    )
                    VALUES (
                        :id,
                        :company_id,
                        :profile_id,
                        :profile_reference_hash,
                        :request_type,
                        'received',
                        :reason_code,
                        :request_reference_hash,
                        CAST(:scope AS jsonb),
                        false,
                        :due_at,
                        :actor_user_id,
                        :requested_at,
                        '{}'::jsonb
                    )
                    RETURNING *
                    """
                ),
                {
                    "id": request_id,
                    "company_id": company_id,
                    "profile_id": payload.profile_id,
                    "profile_reference_hash": privacy_reference_fingerprint(
                        company_id,
                        str(payload.profile_id),
                    ),
                    "request_type": payload.request_type,
                    "reason_code": payload.reason_code,
                    "request_reference_hash": privacy_reference_fingerprint(
                        company_id,
                        payload.request_reference,
                    ),
                    "scope": json.dumps(payload.scope),
                    "due_at": requested_at + timedelta(days=payload.due_days),
                    "actor_user_id": actor_user_id,
                    "requested_at": requested_at,
                },
            )
        )
        .mappings()
        .one()
    )
    await _privacy_event(
        database,
        company_id=company_id,
        request_id=request_id,
        actor_user_id=actor_user_id,
        event_type="request.created",
        previous_status=None,
        new_status="received",
    )
    return _request_response(row)


async def verify_customer_privacy_identity(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
) -> CustomerPrivacyRequestResponse:
    row = (
        (
            await database.execute(
                text(
                    """
                    UPDATE customer_privacy_requests
                    SET status = 'identity_verified',
                        verified_by_user_id = :actor_user_id,
                        verified_at = now()
                    WHERE id = :request_id
                      AND company_id = :company_id
                      AND status = 'received'
                    RETURNING *
                    """
                ),
                {
                    "company_id": company_id,
                    "request_id": request_id,
                    "actor_user_id": actor_user_id,
                },
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ValueError("Somente solicitacoes recebidas podem ser verificadas.")
    await _privacy_event(
        database,
        company_id=company_id,
        request_id=request_id,
        actor_user_id=actor_user_id,
        event_type="identity.verified",
        previous_status="received",
        new_status="identity_verified",
    )
    return _request_response(row)


async def decide_customer_privacy_request(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    payload: CustomerPrivacyDecisionRequest,
) -> CustomerPrivacyRequestResponse:
    row = (
        (
            await database.execute(
                text(
                    """
                    UPDATE customer_privacy_requests
                    SET status = :decision,
                        reason_code = :reason_code,
                        decided_by_user_id = :actor_user_id,
                        decided_at = now()
                    WHERE id = :request_id
                      AND company_id = :company_id
                      AND status = 'identity_verified'
                    RETURNING *
                    """
                ),
                {
                    "company_id": company_id,
                    "request_id": request_id,
                    "decision": payload.decision,
                    "reason_code": payload.reason_code,
                    "actor_user_id": actor_user_id,
                },
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ValueError("A decisao exige identidade previamente verificada.")
    await _privacy_event(
        database,
        company_id=company_id,
        request_id=request_id,
        actor_user_id=actor_user_id,
        event_type=f"request.{payload.decision}",
        previous_status="identity_verified",
        new_status=payload.decision,
    )
    return _request_response(row)


async def set_customer_privacy_legal_hold(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    payload: CustomerPrivacyLegalHoldRequest,
) -> CustomerPrivacyRequestResponse:
    row = (
        (
            await database.execute(
                text(
                    """
                    UPDATE customer_privacy_requests
                    SET legal_hold = :enabled,
                        legal_hold_reason = :reason,
                        legal_hold_by_user_id = CASE
                            WHEN :enabled THEN :actor_user_id
                            ELSE NULL
                        END,
                        legal_hold_at = CASE
                            WHEN :enabled THEN now()
                            ELSE NULL
                        END
                    WHERE id = :request_id
                      AND company_id = :company_id
                      AND status <> 'completed'
                    RETURNING *
                    """
                ),
                {
                    "company_id": company_id,
                    "request_id": request_id,
                    "enabled": payload.enabled,
                    "reason": payload.reason if payload.enabled else None,
                    "actor_user_id": actor_user_id,
                },
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ValueError("Solicitacao concluida nao aceita retencao legal.")
    await _privacy_event(
        database,
        company_id=company_id,
        request_id=request_id,
        actor_user_id=actor_user_id,
        event_type="legal_hold.enabled" if payload.enabled else "legal_hold.released",
        previous_status=row["status"],
        new_status=row["status"],
    )
    return _request_response(row)


def _affected(result: Any) -> int:
    rowcount = getattr(result, "rowcount", 0)
    return max(int(rowcount or 0), 0)


async def execute_customer_privacy_request(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
) -> CustomerPrivacyRequestResponse:
    await database.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:request_key, 0))"),
        {"request_key": str(request_id)},
    )
    request_row = (
        (
            await database.execute(
                text(
                    """
                    SELECT *
                    FROM customer_privacy_requests
                    WHERE id = :request_id
                      AND company_id = :company_id
                    FOR UPDATE
                    """
                ),
                {"company_id": company_id, "request_id": request_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if request_row is None:
        raise LookupError("Solicitacao de privacidade nao encontrada.")
    if request_row["status"] != "approved":
        raise ValueError("Somente solicitacoes aprovadas podem ser executadas.")
    if request_row["legal_hold"]:
        raise ValueError("A retencao legal bloqueia a remocao de dados.")
    profile_id = request_row["profile_id"]
    if profile_id is None:
        raise ValueError("O perfil ja foi removido.")

    contact_rows = (
        await database.execute(
            text(
                """
                SELECT contact_id
                FROM customer_profile_contacts
                WHERE company_id = :company_id
                  AND profile_id = :profile_id
                """
            ),
            {"company_id": company_id, "profile_id": profile_id},
        )
    ).all()
    contact_ids = [row.contact_id for row in contact_rows]
    counts: dict[str, int] = {}

    if contact_ids:
        counts["contact_tags_removed"] = _affected(
            await database.execute(
                text(
                    """
                    DELETE FROM crm_contact_tags
                    WHERE contact_id = ANY(CAST(:contact_ids AS uuid[]))
                    """
                ),
                {"contact_ids": contact_ids},
            )
        )
        counts["campaign_links_removed"] = _affected(
            await database.execute(
                text(
                    """
                    DELETE FROM marketing_campaign_contacts
                    WHERE contact_id = ANY(CAST(:contact_ids AS uuid[]))
                    """
                ),
                {"contact_ids": contact_ids},
            )
        )
        unlink_statements = (
            (
                "support_tickets_unlinked",
                text(
                    """
                    UPDATE support_tickets
                    SET requester_contact_id = NULL
                    WHERE company_id = :company_id
                      AND requester_contact_id = ANY(CAST(:contact_ids AS uuid[]))
                    """
                ),
            ),
            (
                "crm_opportunities_unlinked",
                text(
                    """
                    UPDATE crm_opportunities
                    SET contact_id = NULL
                    WHERE company_id = :company_id
                      AND contact_id = ANY(CAST(:contact_ids AS uuid[]))
                    """
                ),
            ),
            (
                "crm_opportunity_activities_unlinked",
                text(
                    """
                    UPDATE crm_opportunity_activities
                    SET contact_id = NULL
                    WHERE company_id = :company_id
                      AND contact_id = ANY(CAST(:contact_ids AS uuid[]))
                    """
                ),
            ),
            (
                "marketing_attributions_unlinked",
                text(
                    """
                    UPDATE marketing_attributions
                    SET contact_id = NULL
                    WHERE company_id = :company_id
                      AND contact_id = ANY(CAST(:contact_ids AS uuid[]))
                    """
                ),
            ),
        )
        for count_key, statement in unlink_statements:
            result = await database.execute(
                statement,
                {"company_id": company_id, "contact_ids": contact_ids},
            )
            counts[count_key] = _affected(result)
        counts["contacts_anonymized"] = _affected(
            await database.execute(
                text(
                    """
                    UPDATE crm_contacts
                    SET name = 'Titular anonimizado',
                        email = NULL,
                        phone = NULL,
                        company_name = NULL,
                        job_title = NULL,
                        source = NULL,
                        status = 'inactive',
                        assigned_user_id = NULL,
                        updated_at = now()
                    WHERE company_id = :company_id
                      AND id = ANY(CAST(:contact_ids AS uuid[]))
                    """
                ),
                {"company_id": company_id, "contact_ids": contact_ids},
            )
        )

    counts["identities_anonymized"] = _affected(
        await database.execute(
            text(
                """
                UPDATE customer_identities
                SET value_hash = encode(
                        digest(
                            company_id::text || ':' || id::text || ':' || :request_id,
                            'sha256'
                        ),
                        'hex'
                    ),
                    display_hint = 'anonimizado',
                    verified = false
                WHERE company_id = :company_id
                  AND profile_id = :profile_id
                """
            ),
            {
                "company_id": company_id,
                "profile_id": profile_id,
                "request_id": str(request_id),
            },
        )
    )
    counts["consents_revoked"] = _affected(
        await database.execute(
            text(
                """
                UPDATE customer_consents
                SET status = 'revoked',
                    evidence_reference = NULL
                WHERE company_id = :company_id
                  AND profile_id = :profile_id
                """
            ),
            {"company_id": company_id, "profile_id": profile_id},
        )
    )
    counts["lineage_anonymized"] = _affected(
        await database.execute(
            text(
                """
                UPDATE customer_field_lineage
                SET value_fingerprint = encode(
                        digest(id::text || ':' || :request_id, 'sha256'),
                        'hex'
                    ),
                    source_record_id = 'anon-' || left(
                        encode(
                            digest(id::text || ':' || :request_id, 'sha256'),
                            'hex'
                        ),
                        32
                    ),
                    classification = 'restricted'
                WHERE company_id = :company_id
                  AND profile_id = :profile_id
                """
            ),
            {
                "company_id": company_id,
                "profile_id": profile_id,
                "request_id": str(request_id),
            },
        )
    )
    counts["ingestion_records_anonymized"] = _affected(
        await database.execute(
            text(
                """
                UPDATE customer_ingestion_records
                SET source_record_id = 'anon-' || left(
                        encode(
                            digest(id::text || ':' || :request_id, 'sha256'),
                            'hex'
                        ),
                        32
                    ),
                    payload_hash = encode(
                        digest(id::text || ':' || :request_id, 'sha256'),
                        'hex'
                    ),
                    errors = '[]'::jsonb
                WHERE company_id = :company_id
                  AND profile_id = :profile_id
                """
            ),
            {
                "company_id": company_id,
                "profile_id": profile_id,
                "request_id": str(request_id),
            },
        )
    )
    counts["cdc_events_anonymized"] = _affected(
        await database.execute(
            text(
                """
                UPDATE customer_change_events
                SET profile_id = NULL,
                    source_record_fingerprint = encode(
                        digest(id::text || ':source:' || :request_id, 'sha256'),
                        'hex'
                    ),
                    payload_fingerprint = encode(
                        digest(id::text || ':payload:' || :request_id, 'sha256'),
                        'hex'
                    ),
                    changed_fields = '["privacy_erasure"]'::jsonb,
                    operation = 'deleted'
                WHERE company_id = :company_id
                  AND profile_id = :profile_id
                """
            ),
            {
                "company_id": company_id,
                "profile_id": profile_id,
                "request_id": str(request_id),
            },
        )
    )
    counts["merge_cases_sanitized"] = _affected(
        await database.execute(
            text(
                """
                UPDATE customer_profile_merge_cases
                SET decision_note = NULL,
                    reasons = '["Conteudo removido por politica de privacidade."]'::jsonb
                WHERE company_id = :company_id
                  AND (
                      primary_profile_id = :profile_id
                      OR secondary_profile_id = :profile_id
                  )
                """
            ),
            {"company_id": company_id, "profile_id": profile_id},
        )
    )

    if request_row["request_type"] == "deletion":
        counts["merge_cases_removed"] = _affected(
            await database.execute(
                text(
                    """
                    DELETE FROM customer_profile_merge_cases
                    WHERE company_id = :company_id
                      AND (
                          primary_profile_id = :profile_id
                          OR secondary_profile_id = :profile_id
                      )
                    """
                ),
                {"company_id": company_id, "profile_id": profile_id},
            )
        )
        counts["profiles_deleted"] = _affected(
            await database.execute(
                text(
                    """
                    DELETE FROM customer_profiles
                    WHERE company_id = :company_id
                      AND id = :profile_id
                    """
                ),
                {"company_id": company_id, "profile_id": profile_id},
            )
        )
        if contact_ids:
            counts["contacts_deleted"] = _affected(
                await database.execute(
                    text(
                        """
                        DELETE FROM crm_contacts
                        WHERE company_id = :company_id
                          AND id = ANY(CAST(:contact_ids AS uuid[]))
                        """
                    ),
                    {"company_id": company_id, "contact_ids": contact_ids},
                )
            )
    else:
        counts["profiles_anonymized"] = _affected(
            await database.execute(
                text(
                    """
                    UPDATE customer_profiles
                    SET display_name = 'Titular anonimizado',
                        lifecycle_status = 'inactive',
                        quality_score = 0,
                        master_contact_id = NULL,
                        updated_at = now()
                    WHERE company_id = :company_id
                      AND id = :profile_id
                    """
                ),
                {"company_id": company_id, "profile_id": profile_id},
            )
        )

    completed_row = (
        (
            await database.execute(
                text(
                    """
                    UPDATE customer_privacy_requests
                    SET status = 'completed',
                        executed_by_user_id = :actor_user_id,
                        completed_at = now(),
                        result_counts = CAST(:result_counts AS jsonb)
                    WHERE id = :request_id
                      AND company_id = :company_id
                    RETURNING *
                    """
                ),
                {
                    "company_id": company_id,
                    "request_id": request_id,
                    "actor_user_id": actor_user_id,
                    "result_counts": json.dumps(counts),
                },
            )
        )
        .mappings()
        .one()
    )
    await _privacy_event(
        database,
        company_id=company_id,
        request_id=request_id,
        actor_user_id=actor_user_id,
        event_type=f"{request_row['request_type']}.completed",
        previous_status="approved",
        new_status="completed",
    )
    return _request_response(completed_row)


async def get_customer_privacy_summary(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> CustomerPrivacySummaryResponse:
    row = (
        (
            await database.execute(
                text(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE status = 'received')::integer
                            AS received,
                        COUNT(*) FILTER (WHERE status = 'identity_verified')::integer
                            AS awaiting_decision,
                        COUNT(*) FILTER (WHERE status = 'approved')::integer
                            AS approved,
                        COUNT(*) FILTER (
                            WHERE status = 'approved' AND legal_hold
                        )::integer AS blocked_by_legal_hold,
                        COUNT(*) FILTER (WHERE status = 'completed')::integer
                            AS completed,
                        COUNT(*) FILTER (
                            WHERE status NOT IN ('rejected', 'completed')
                              AND due_at < now()
                        )::integer AS overdue
                    FROM customer_privacy_requests
                    WHERE company_id = :company_id
                    """
                ),
                {"company_id": company_id},
            )
        )
        .mappings()
        .one()
    )
    return CustomerPrivacySummaryResponse(**row)
