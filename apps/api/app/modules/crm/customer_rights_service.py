from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.customer_rights_schemas import (
    CustomerCorrectionRequest,
    CustomerCorrectionResponse,
    CustomerProcessingRestrictionCreate,
    CustomerProcessingRestrictionResponse,
    CustomerRightsSummaryResponse,
    CustomerSubjectActivitySummary,
    CustomerSubjectConsentExport,
    CustomerSubjectContactExport,
    CustomerSubjectExportResponse,
    CustomerSubjectIdentityExport,
    CustomerSubjectProfileExport,
)


def _identity_hash(value: str) -> str:
    return hashlib.sha256(value.strip().casefold().encode()).hexdigest()


def _display_hint(value: str, identity_type: str) -> str:
    normalized = value.strip()
    if identity_type == "email" and "@" in normalized:
        local, domain = normalized.split("@", 1)
        return f"{local[:2]}***@{domain}"
    digits = "".join(character for character in normalized if character.isdigit())
    if identity_type == "phone" and digits:
        return f"***{digits[-4:]}"
    return f"{normalized[:2]}***"


async def _profile(database: AsyncSession, *, company_id: UUID, profile_id: UUID) -> Any:
    row = (
        await database.execute(
            text(
                """
                SELECT
                    profile.id, profile.display_name, profile.profile_type,
                    profile.lifecycle_status, profile.quality_score, profile.status,
                    profile.master_contact_id,
                    contact.name, contact.email, contact.phone, contact.company_name,
                    contact.job_title, contact.status AS contact_status
                FROM customer_profiles AS profile
                LEFT JOIN crm_contacts AS contact
                  ON contact.company_id = profile.company_id
                 AND contact.id = profile.master_contact_id
                 AND contact.deleted_at IS NULL
                WHERE profile.company_id = :company_id
                  AND profile.id = :profile_id
                  AND profile.status <> 'deleted'
                """
            ),
            {"company_id": company_id, "profile_id": profile_id},
        )
    ).mappings().one_or_none()
    if row is None:
        raise LookupError("Perfil de cliente não encontrado.")
    return row


async def _audit(
    database: AsyncSession,
    *,
    company_id: UUID,
    profile_id: UUID,
    actor_user_id: UUID,
    operation_type: str,
    field_names: list[str] | None = None,
) -> None:
    await database.execute(
        text(
            """
            INSERT INTO customer_privacy_right_operations (
                id, company_id, profile_id, operation_type, outcome,
                field_names, performed_by_user_id
            ) VALUES (
                :id, :company_id, :profile_id, :operation_type, 'completed',
                CAST(:field_names AS jsonb), :actor_user_id
            )
            """
        ),
        {
            "id": uuid4(),
            "company_id": company_id,
            "profile_id": profile_id,
            "operation_type": operation_type,
            "field_names": json.dumps(sorted(field_names or [])),
            "actor_user_id": actor_user_id,
        },
    )


async def _restriction_response(
    database: AsyncSession,
    *,
    company_id: UUID,
    profile_id: UUID,
) -> CustomerProcessingRestrictionResponse:
    row = (
        await database.execute(
            text(
                """
                SELECT id, profile_id, status, reason_code, enforced_at, released_at
                FROM customer_processing_restrictions
                WHERE company_id = :company_id AND profile_id = :profile_id
                """
            ),
            {"company_id": company_id, "profile_id": profile_id},
        )
    ).mappings().one()
    return CustomerProcessingRestrictionResponse.model_validate(row)


async def get_customer_rights_summary(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> CustomerRightsSummaryResponse:
    row = (
        await database.execute(
            text(
                """
                SELECT
                    (
                        SELECT count(*)
                        FROM customer_processing_restrictions
                        WHERE company_id = :company_id AND status = 'active'
                    ) AS active_restrictions,
                    (
                        SELECT count(*)
                        FROM customer_privacy_right_operations
                        WHERE company_id = :company_id
                          AND operation_type = 'access_export'
                          AND created_at >= now() - interval '30 days'
                    ) AS exports_last_30_days,
                    (
                        SELECT count(*)
                        FROM customer_privacy_right_operations
                        WHERE company_id = :company_id
                          AND operation_type = 'correction'
                          AND created_at >= now() - interval '30 days'
                    ) AS corrections_last_30_days
                """
            ),
            {"company_id": company_id},
        )
    ).mappings().one()
    return CustomerRightsSummaryResponse.model_validate(row)


async def list_processing_restrictions(
    database: AsyncSession,
    *,
    company_id: UUID,
    active_only: bool = True,
) -> list[CustomerProcessingRestrictionResponse]:
    rows = (
        await database.execute(
            text(
                """
                SELECT id, profile_id, status, reason_code, enforced_at, released_at
                FROM customer_processing_restrictions
                WHERE company_id = :company_id
                  AND (CAST(:active_only AS boolean) = false OR status = 'active')
                ORDER BY enforced_at DESC
                LIMIT 200
                """
            ),
            {"company_id": company_id, "active_only": active_only},
        )
    ).mappings().all()
    return [
        CustomerProcessingRestrictionResponse.model_validate(row)
        for row in rows
    ]


async def restrict_customer_processing(
    database: AsyncSession,
    *,
    company_id: UUID,
    profile_id: UUID,
    actor_user_id: UUID,
    payload: CustomerProcessingRestrictionCreate,
) -> CustomerProcessingRestrictionResponse:
    await _profile(database, company_id=company_id, profile_id=profile_id)
    await database.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"customer-restriction:{company_id}:{profile_id}"},
    )
    await database.execute(
        text(
            """
            INSERT INTO customer_processing_restrictions (
                id, company_id, profile_id, status, reason_code,
                requested_by_user_id, enforced_by_user_id,
                enforced_at, released_by_user_id, released_at
            ) VALUES (
                :id, :company_id, :profile_id, 'active', :reason_code,
                :actor_user_id, :actor_user_id, now(), NULL, NULL
            )
            ON CONFLICT (company_id, profile_id) DO UPDATE
            SET status = 'active',
                reason_code = EXCLUDED.reason_code,
                requested_by_user_id = EXCLUDED.requested_by_user_id,
                enforced_by_user_id = EXCLUDED.enforced_by_user_id,
                enforced_at = now(),
                released_by_user_id = NULL,
                released_at = NULL,
                updated_at = now()
            """
        ),
        {
            "id": uuid4(),
            "company_id": company_id,
            "profile_id": profile_id,
            "reason_code": payload.reason_code,
            "actor_user_id": actor_user_id,
        },
    )
    await _audit(
        database,
        company_id=company_id,
        profile_id=profile_id,
        actor_user_id=actor_user_id,
        operation_type="restriction",
    )
    return await _restriction_response(
        database,
        company_id=company_id,
        profile_id=profile_id,
    )


async def release_customer_processing_restriction(
    database: AsyncSession,
    *,
    company_id: UUID,
    profile_id: UUID,
    actor_user_id: UUID,
) -> CustomerProcessingRestrictionResponse:
    await database.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"customer-restriction:{company_id}:{profile_id}"},
    )
    result = await database.execute(
        text(
            """
            UPDATE customer_processing_restrictions
            SET status = 'released',
                released_by_user_id = :actor_user_id,
                released_at = now(),
                updated_at = now()
            WHERE company_id = :company_id
              AND profile_id = :profile_id
              AND status = 'active'
            RETURNING id
            """
        ),
        {
            "company_id": company_id,
            "profile_id": profile_id,
            "actor_user_id": actor_user_id,
        },
    )
    if result.scalar_one_or_none() is None:
        raise LookupError("Restrição ativa não encontrada.")
    await _audit(
        database,
        company_id=company_id,
        profile_id=profile_id,
        actor_user_id=actor_user_id,
        operation_type="restriction_release",
    )
    return await _restriction_response(
        database,
        company_id=company_id,
        profile_id=profile_id,
    )


async def correct_customer_subject(
    database: AsyncSession,
    *,
    company_id: UUID,
    profile_id: UUID,
    actor_user_id: UUID,
    payload: CustomerCorrectionRequest,
) -> CustomerCorrectionResponse:
    profile = await _profile(database, company_id=company_id, profile_id=profile_id)
    fields = sorted(payload.model_fields_set)
    contact_fields = {"name", "email", "phone", "company_name", "job_title"}
    if contact_fields.intersection(fields) and profile["master_contact_id"] is None:
        raise ValueError("O perfil não possui contato principal para correção.")

    await database.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"customer-correction:{company_id}:{profile_id}"},
    )
    await database.execute(
        text(
            """
            UPDATE customer_profiles
            SET display_name = CASE
                    WHEN CAST(:display_name_set AS boolean) THEN :display_name
                    ELSE display_name
                END,
                updated_at = now()
            WHERE company_id = :company_id AND id = :profile_id
            """
        ),
        {
            "company_id": company_id,
            "profile_id": profile_id,
            "display_name_set": "display_name" in fields,
            "display_name": payload.display_name,
        },
    )
    if profile["master_contact_id"] is not None:
        await database.execute(
            text(
                """
                UPDATE crm_contacts
                SET name = CASE WHEN CAST(:name_set AS boolean) THEN :name ELSE name END,
                    email = CASE WHEN CAST(:email_set AS boolean) THEN :email ELSE email END,
                    phone = CASE WHEN CAST(:phone_set AS boolean) THEN :phone ELSE phone END,
                    company_name = CASE
                        WHEN CAST(:company_name_set AS boolean) THEN :company_name
                        ELSE company_name
                    END,
                    job_title = CASE
                        WHEN CAST(:job_title_set AS boolean) THEN :job_title
                        ELSE job_title
                    END,
                    updated_at = now()
                WHERE company_id = :company_id
                  AND id = :contact_id
                  AND deleted_at IS NULL
                """
            ),
            {
                "company_id": company_id,
                "contact_id": profile["master_contact_id"],
                "name_set": "name" in fields,
                "name": payload.name,
                "email_set": "email" in fields,
                "email": payload.email,
                "phone_set": "phone" in fields,
                "phone": payload.phone,
                "company_name_set": "company_name" in fields,
                "company_name": payload.company_name,
                "job_title_set": "job_title" in fields,
                "job_title": payload.job_title,
            },
        )

    identity_values = {"email": payload.email, "phone": payload.phone}
    if any(name in fields for name in identity_values):
        source_id = await database.scalar(
            text(
                """
                INSERT INTO customer_data_sources (
                    id, company_id, code, name, mode, status
                ) VALUES (
                    :id, :company_id, 'privacy-rights',
                    'Direitos do titular', 'system_of_record', 'active'
                )
                ON CONFLICT (company_id, code) DO UPDATE SET updated_at = now()
                RETURNING id
                """
            ),
            {"id": uuid4(), "company_id": company_id},
        )
        for identity_type, value in identity_values.items():
            if identity_type not in fields or value is None:
                continue
            await database.execute(
                text(
                    """
                    UPDATE customer_identities
                    SET verified = false
                    WHERE company_id = :company_id
                      AND profile_id = :profile_id
                      AND identity_type = :identity_type
                    """
                ),
                {
                    "company_id": company_id,
                    "profile_id": profile_id,
                    "identity_type": identity_type,
                },
            )
            await database.execute(
                text(
                    """
                    INSERT INTO customer_identities (
                        id, company_id, profile_id, data_source_id, identity_type,
                        value_hash, display_hint, verified
                    ) VALUES (
                        :id, :company_id, :profile_id, :source_id, :identity_type,
                        :value_hash, :display_hint, true
                    )
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "id": uuid4(),
                    "company_id": company_id,
                    "profile_id": profile_id,
                    "source_id": source_id,
                    "identity_type": identity_type,
                    "value_hash": _identity_hash(value),
                    "display_hint": _display_hint(value, identity_type),
                },
            )

    await _audit(
        database,
        company_id=company_id,
        profile_id=profile_id,
        actor_user_id=actor_user_id,
        operation_type="correction",
        field_names=fields,
    )
    return CustomerCorrectionResponse(
        profile_id=profile_id,
        applied_fields=fields,
        corrected_at=datetime.now(UTC),
    )


async def export_customer_subject(
    database: AsyncSession,
    *,
    company_id: UUID,
    profile_id: UUID,
    actor_user_id: UUID,
) -> CustomerSubjectExportResponse:
    row = await _profile(database, company_id=company_id, profile_id=profile_id)
    identities = (
        await database.execute(
            text(
                """
                SELECT identity_type, display_hint, verified, created_at
                FROM customer_identities
                WHERE company_id = :company_id AND profile_id = :profile_id
                ORDER BY identity_type, created_at
                """
            ),
            {"company_id": company_id, "profile_id": profile_id},
        )
    ).mappings().all()
    consents = (
        await database.execute(
            text(
                """
                SELECT purpose, channel, status, lawful_basis,
                       evidence_reference IS NOT NULL AS evidence_available,
                       captured_at, expires_at
                FROM customer_consents
                WHERE company_id = :company_id AND profile_id = :profile_id
                ORDER BY captured_at DESC
                """
            ),
            {"company_id": company_id, "profile_id": profile_id},
        )
    ).mappings().all()
    counts = (
        await database.execute(
            text(
                """
                SELECT
                    (
                        SELECT count(*) FROM support_tickets
                        WHERE company_id = :company_id
                          AND requester_contact_id = :contact_id
                    ) AS support_tickets,
                    (
                        SELECT count(*) FROM crm_opportunities
                        WHERE company_id = :company_id AND contact_id = :contact_id
                    ) AS opportunities,
                    (
                        SELECT count(*) FROM marketing_attributions
                        WHERE company_id = :company_id AND contact_id = :contact_id
                    ) AS marketing_attributions,
                    (
                        SELECT count(*) FROM customer_privacy_requests
                        WHERE company_id = :company_id AND profile_id = :profile_id
                    ) AS privacy_requests
                """
            ),
            {
                "company_id": company_id,
                "profile_id": profile_id,
                "contact_id": row["master_contact_id"],
            },
        )
    ).mappings().one()
    restricted = bool(
        await database.scalar(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM customer_processing_restrictions
                    WHERE company_id = :company_id
                      AND profile_id = :profile_id
                      AND status = 'active'
                )
                """
            ),
            {"company_id": company_id, "profile_id": profile_id},
        )
    )

    profile = CustomerSubjectProfileExport(
        id=row["id"],
        display_name=row["display_name"],
        profile_type=row["profile_type"],
        lifecycle_status=row["lifecycle_status"],
        quality_score=row["quality_score"],
        status=row["status"],
    )
    contact = (
        CustomerSubjectContactExport(
            id=row["master_contact_id"],
            name=row["name"],
            email=row["email"],
            phone=row["phone"],
            company_name=row["company_name"],
            job_title=row["job_title"],
            status=row["contact_status"],
        )
        if row["master_contact_id"] is not None
        else None
    )
    identity_models = [
        CustomerSubjectIdentityExport.model_validate(identity) for identity in identities
    ]
    consent_models = [
        CustomerSubjectConsentExport.model_validate(consent) for consent in consents
    ]
    activity = CustomerSubjectActivitySummary.model_validate(counts)
    digest_payload = {
        "profile": profile.model_dump(mode="json"),
        "contact": contact.model_dump(mode="json") if contact else None,
        "identities": [item.model_dump(mode="json") for item in identity_models],
        "consents": [item.model_dump(mode="json") for item in consent_models],
        "activity_summary": activity.model_dump(mode="json"),
        "processing_restricted": restricted,
    }
    digest = hashlib.sha256(
        json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    await _audit(
        database,
        company_id=company_id,
        profile_id=profile_id,
        actor_user_id=actor_user_id,
        operation_type="access_export",
    )
    return CustomerSubjectExportResponse(
        generated_at=datetime.now(UTC),
        profile=profile,
        contact=contact,
        identities=identity_models,
        consents=consent_models,
        activity_summary=activity,
        processing_restricted=restricted,
        integrity_sha256=digest,
    )
