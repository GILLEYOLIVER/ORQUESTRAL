from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.customer_segment_schemas import (
    CustomerProfileSearchResponse,
    CustomerProfileSearchResult,
    CustomerSegmentActivationRequest,
    CustomerSegmentActivationResponse,
    CustomerSegmentCreate,
    CustomerSegmentDefinition,
    CustomerSegmentMaterializationResponse,
    CustomerSegmentResponse,
)


def _segment_response(row: Any) -> CustomerSegmentResponse:
    return CustomerSegmentResponse(
        id=row.id,
        name=row.name,
        description=row.description,
        status=row.status,
        version=row.version,
        definition=CustomerSegmentDefinition.model_validate(row.definition_json),
        member_count=row.member_count,
        materialized_at=row.materialized_at,
        published_at=row.published_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _segment(
    database: AsyncSession,
    *,
    company_id: UUID,
    segment_id: UUID,
) -> Any:
    row = (
        await database.execute(
            text(
                """
                SELECT id, name, description, status, version, definition_json,
                       member_count, materialized_at, published_at, created_at, updated_at
                FROM customer_segments
                WHERE company_id = :company_id AND id = :segment_id
                """
            ),
            {"company_id": company_id, "segment_id": segment_id},
        )
    ).one_or_none()
    if row is None:
        raise LookupError("Segmento não encontrado.")
    return row


async def list_customer_segments(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> list[CustomerSegmentResponse]:
    rows = (
        await database.execute(
            text(
                """
                SELECT id, name, description, status, version, definition_json,
                       member_count, materialized_at, published_at, created_at, updated_at
                FROM customer_segments
                WHERE company_id = :company_id
                ORDER BY updated_at DESC
                LIMIT 200
                """
            ),
            {"company_id": company_id},
        )
    ).all()
    return [_segment_response(row) for row in rows]


async def create_customer_segment(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    payload: CustomerSegmentCreate,
) -> CustomerSegmentResponse:
    row = (
        await database.execute(
            text(
                """
                INSERT INTO customer_segments (
                    id, company_id, name, description, status, version,
                    definition_json, created_by_user_id
                ) VALUES (
                    :id, :company_id, :name, :description, 'draft', 1,
                    CAST(:definition AS jsonb), :actor_user_id
                )
                RETURNING id, name, description, status, version, definition_json,
                          member_count, materialized_at, published_at, created_at, updated_at
                """
            ),
            {
                "id": uuid4(),
                "company_id": company_id,
                "name": payload.name.strip(),
                "description": payload.description.strip() if payload.description else None,
                "definition": json.dumps(payload.definition.model_dump(mode="json")),
                "actor_user_id": actor_user_id,
            },
        )
    ).one()
    return _segment_response(row)


async def materialize_customer_segment(
    database: AsyncSession,
    *,
    company_id: UUID,
    segment_id: UUID,
) -> CustomerSegmentMaterializationResponse:
    segment = await _segment(database, company_id=company_id, segment_id=segment_id)
    definition = CustomerSegmentDefinition.model_validate(segment.definition_json)
    await database.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"customer-segment:{company_id}:{segment_id}"},
    )
    excluded_restricted = int(
        await database.scalar(
            text(
                """
                SELECT count(*)
                FROM customer_profiles AS profile
                WHERE profile.company_id = :company_id
                  AND profile.status = 'active'
                  AND (
                      CAST(:profile_type AS VARCHAR) IS NULL
                      OR profile.profile_type = CAST(:profile_type AS VARCHAR)
                  )
                  AND (
                      CAST(:lifecycle_status AS VARCHAR) IS NULL
                      OR profile.lifecycle_status = CAST(:lifecycle_status AS VARCHAR)
                  )
                  AND profile.quality_score >= :min_quality_score
                  AND EXISTS (
                      SELECT 1
                      FROM customer_processing_restrictions AS restriction
                      WHERE restriction.company_id = profile.company_id
                        AND restriction.profile_id = profile.id
                        AND restriction.status = 'active'
                  )
                """
            ),
            {
                "company_id": company_id,
                "profile_type": definition.profile_type,
                "lifecycle_status": definition.lifecycle_status,
                "min_quality_score": definition.min_quality_score,
            },
        )
        or 0
    )
    await database.execute(
        text(
            """
            DELETE FROM customer_segment_members
            WHERE company_id = :company_id AND segment_id = :segment_id
            """
        ),
        {"company_id": company_id, "segment_id": segment_id},
    )
    inserted = (
        await database.execute(
            text(
                """
                INSERT INTO customer_segment_members (
                    id, company_id, segment_id, profile_id, contact_id, matched_at
                )
                SELECT
                    gen_random_uuid(), profile.company_id, :segment_id,
                    profile.id, profile.master_contact_id, now()
                FROM customer_profiles AS profile
                WHERE profile.company_id = :company_id
                  AND profile.status = 'active'
                  AND (
                      CAST(:profile_type AS VARCHAR) IS NULL
                      OR profile.profile_type = CAST(:profile_type AS VARCHAR)
                  )
                  AND (
                      CAST(:lifecycle_status AS VARCHAR) IS NULL
                      OR profile.lifecycle_status = CAST(:lifecycle_status AS VARCHAR)
                  )
                  AND profile.quality_score >= :min_quality_score
                  AND NOT EXISTS (
                      SELECT 1
                      FROM customer_processing_restrictions AS restriction
                      WHERE restriction.company_id = profile.company_id
                        AND restriction.profile_id = profile.id
                        AND restriction.status = 'active'
                  )
                  AND (
                      CAST(:consent_purpose AS VARCHAR) IS NULL
                      OR EXISTS (
                          SELECT 1
                          FROM customer_consents AS consent
                          WHERE consent.company_id = profile.company_id
                            AND consent.profile_id = profile.id
                            AND consent.status = 'granted'
                            AND consent.purpose = CAST(:consent_purpose AS VARCHAR)
                            AND (
                                CAST(:consent_channel AS VARCHAR) = 'all'
                                OR consent.channel IN (
                                    'all',
                                    CAST(:consent_channel AS VARCHAR)
                                )
                            )
                            AND (
                                consent.expires_at IS NULL
                                OR consent.expires_at > now()
                            )
                      )
                  )
                RETURNING profile_id
                """
            ),
            {
                "company_id": company_id,
                "segment_id": segment_id,
                "profile_type": definition.profile_type,
                "lifecycle_status": definition.lifecycle_status,
                "min_quality_score": definition.min_quality_score,
                "consent_purpose": definition.consent_purpose,
                "consent_channel": definition.consent_channel,
            },
        )
    ).all()
    materialized_at = datetime.now(UTC)
    member_count = len(inserted)
    await database.execute(
        text(
            """
            UPDATE customer_segments
            SET member_count = :member_count,
                materialized_at = :materialized_at,
                updated_at = now()
            WHERE company_id = :company_id AND id = :segment_id
            """
        ),
        {
            "company_id": company_id,
            "segment_id": segment_id,
            "member_count": member_count,
            "materialized_at": materialized_at,
        },
    )
    return CustomerSegmentMaterializationResponse(
        segment_id=segment_id,
        member_count=member_count,
        excluded_restricted_count=excluded_restricted,
        materialized_at=materialized_at,
    )


async def publish_customer_segment(
    database: AsyncSession,
    *,
    company_id: UUID,
    segment_id: UUID,
) -> CustomerSegmentResponse:
    segment = await _segment(database, company_id=company_id, segment_id=segment_id)
    if segment.materialized_at is None:
        raise ValueError("Materialize o segmento antes de publicar.")
    row = (
        await database.execute(
            text(
                """
                UPDATE customer_segments
                SET status = 'published',
                    version = version + 1,
                    published_at = now(),
                    updated_at = now()
                WHERE company_id = :company_id AND id = :segment_id
                RETURNING id, name, description, status, version, definition_json,
                          member_count, materialized_at, published_at, created_at, updated_at
                """
            ),
            {"company_id": company_id, "segment_id": segment_id},
        )
    ).one()
    return _segment_response(row)


async def activate_customer_segment(
    database: AsyncSession,
    *,
    company_id: UUID,
    segment_id: UUID,
    actor_user_id: UUID,
    payload: CustomerSegmentActivationRequest,
) -> CustomerSegmentActivationResponse:
    segment = await _segment(database, company_id=company_id, segment_id=segment_id)
    if segment.status != "published":
        raise ValueError("Publique o segmento antes da ativação.")
    campaign = (
        await database.execute(
            text(
                """
                SELECT id, channel, status
                FROM marketing_campaigns
                WHERE company_id = :company_id
                  AND id = :campaign_id
                  AND archived_at IS NULL
                  AND status IN ('draft', 'scheduled', 'active', 'paused')
                """
            ),
            {"company_id": company_id, "campaign_id": payload.campaign_id},
        )
    ).one_or_none()
    if campaign is None:
        raise LookupError("Campanha de destino não encontrada ou encerrada.")

    await database.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"customer-activation:{company_id}:{segment_id}"},
    )
    counts = (
        await database.execute(
            text(
                """
                SELECT
                    count(*) FILTER (
                        WHERE restriction.id IS NOT NULL
                    ) AS restricted_count,
                    count(*) FILTER (
                        WHERE restriction.id IS NULL
                          AND member.contact_id IS NOT NULL
                          AND EXISTS (
                              SELECT 1
                              FROM customer_consents AS consent
                              WHERE consent.company_id = member.company_id
                                AND consent.profile_id = member.profile_id
                                AND consent.purpose = 'marketing'
                                AND consent.status = 'granted'
                                AND (
                                    consent.expires_at IS NULL
                                    OR consent.expires_at > now()
                                )
                                AND (
                                    (
                                        CAST(:channel AS VARCHAR)
                                        IN ('email', 'whatsapp', 'sms')
                                        AND consent.channel IN (
                                            'all',
                                            CAST(:channel AS VARCHAR)
                                        )
                                    )
                                    OR (
                                        CAST(:channel AS VARCHAR)
                                        NOT IN ('email', 'whatsapp', 'sms')
                                        AND consent.channel IN ('all', 'web')
                                    )
                                )
                          )
                    ) AS eligible_count,
                    count(*) AS total_count
                FROM customer_segment_members AS member
                LEFT JOIN customer_processing_restrictions AS restriction
                  ON restriction.company_id = member.company_id
                 AND restriction.profile_id = member.profile_id
                 AND restriction.status = 'active'
                WHERE member.company_id = :company_id
                  AND member.segment_id = :segment_id
                """
            ),
            {
                "company_id": company_id,
                "segment_id": segment_id,
                "channel": campaign.channel,
            },
        )
    ).one()
    restricted_count = int(counts.restricted_count or 0)
    eligible_count = int(counts.eligible_count or 0)
    total_count = int(counts.total_count or 0)
    excluded_no_consent = max(total_count - restricted_count - eligible_count, 0)

    activated = (
        await database.execute(
            text(
                """
                WITH inserted AS (
                    INSERT INTO marketing_campaign_contacts (
                        id, company_id, campaign_id, contact_id, status
                    )
                    SELECT
                        gen_random_uuid(), member.company_id, :campaign_id,
                        member.contact_id, 'planned'
                    FROM customer_segment_members AS member
                    WHERE member.company_id = :company_id
                      AND member.segment_id = :segment_id
                      AND member.contact_id IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1
                          FROM customer_processing_restrictions AS restriction
                          WHERE restriction.company_id = member.company_id
                            AND restriction.profile_id = member.profile_id
                            AND restriction.status = 'active'
                      )
                      AND EXISTS (
                          SELECT 1
                          FROM customer_consents AS consent
                          WHERE consent.company_id = member.company_id
                            AND consent.profile_id = member.profile_id
                            AND consent.purpose = 'marketing'
                            AND consent.status = 'granted'
                            AND (
                                consent.expires_at IS NULL
                                OR consent.expires_at > now()
                            )
                            AND (
                                (
                                    CAST(:channel AS VARCHAR)
                                    IN ('email', 'whatsapp', 'sms')
                                    AND consent.channel IN (
                                        'all',
                                        CAST(:channel AS VARCHAR)
                                    )
                                )
                                OR (
                                    CAST(:channel AS VARCHAR)
                                    NOT IN ('email', 'whatsapp', 'sms')
                                    AND consent.channel IN ('all', 'web')
                                )
                            )
                      )
                    ON CONFLICT (campaign_id, contact_id) DO NOTHING
                    RETURNING id
                )
                SELECT count(*) FROM inserted
                """
            ),
            {
                "company_id": company_id,
                "segment_id": segment_id,
                "campaign_id": payload.campaign_id,
                "channel": campaign.channel,
            },
        )
    ).scalar_one()
    activated_count = int(activated or 0)
    activation_status = (
        "blocked"
        if eligible_count == 0
        else "partial"
        if restricted_count or excluded_no_consent
        else "completed"
    )
    activation_id = uuid4()
    completed_at = datetime.now(UTC)
    await database.execute(
        text(
            """
            INSERT INTO customer_segment_activations (
                id, company_id, segment_id, destination_type, destination_id,
                status, eligible_count, activated_count,
                excluded_restricted_count, excluded_no_consent_count,
                requested_by_user_id, completed_at
            ) VALUES (
                :id, :company_id, :segment_id, 'marketing_campaign', :campaign_id,
                :status, :eligible_count, :activated_count,
                :restricted_count, :no_consent_count,
                :actor_user_id, :completed_at
            )
            """
        ),
        {
            "id": activation_id,
            "company_id": company_id,
            "segment_id": segment_id,
            "campaign_id": payload.campaign_id,
            "status": activation_status,
            "eligible_count": eligible_count,
            "activated_count": activated_count,
            "restricted_count": restricted_count,
            "no_consent_count": excluded_no_consent,
            "actor_user_id": actor_user_id,
            "completed_at": completed_at,
        },
    )
    return CustomerSegmentActivationResponse(
        id=activation_id,
        segment_id=segment_id,
        campaign_id=payload.campaign_id,
        status=activation_status,
        eligible_count=eligible_count,
        activated_count=activated_count,
        excluded_restricted_count=restricted_count,
        excluded_no_consent_count=excluded_no_consent,
        completed_at=completed_at,
    )


async def search_customer_profiles(
    database: AsyncSession,
    *,
    company_id: UUID,
    query: str,
    limit: int,
) -> CustomerProfileSearchResponse:
    normalized = query.strip().casefold()
    digits = "".join(character for character in normalized if character.isdigit())
    identity_type = (
        "email" if "@" in normalized else "phone" if len(digits) >= 6 else None
    )
    identity_value = digits if identity_type == "phone" else normalized
    identity_hash = (
        hashlib.sha256(identity_value.encode()).hexdigest()
        if identity_type is not None
        else None
    )
    rows = (
        await database.execute(
            text(
                """
                SELECT
                    profile.id AS profile_id,
                    profile.display_name,
                    profile.profile_type,
                    profile.lifecycle_status,
                    profile.quality_score,
                    identity.display_hint AS identity_hint,
                    EXISTS (
                        SELECT 1
                        FROM customer_processing_restrictions AS restriction
                        WHERE restriction.company_id = profile.company_id
                          AND restriction.profile_id = profile.id
                          AND restriction.status = 'active'
                    ) AS processing_restricted
                FROM customer_profiles AS profile
                LEFT JOIN LATERAL (
                    SELECT candidate.display_hint
                    FROM customer_identities AS candidate
                    WHERE candidate.company_id = profile.company_id
                      AND candidate.profile_id = profile.id
                    ORDER BY
                        (
                            CAST(:identity_hash AS VARCHAR) IS NOT NULL
                            AND candidate.value_hash = CAST(:identity_hash AS VARCHAR)
                        ) DESC,
                        candidate.verified DESC,
                        candidate.created_at DESC
                    LIMIT 1
                ) AS identity ON true
                WHERE profile.company_id = :company_id
                  AND profile.status = 'active'
                  AND (
                      to_tsvector('simple', coalesce(profile.display_name, ''))
                      @@ plainto_tsquery('simple', :query)
                      OR profile.display_name ILIKE :pattern
                      OR (
                          CAST(:identity_hash AS VARCHAR) IS NOT NULL
                          AND EXISTS (
                              SELECT 1
                              FROM customer_identities AS exact_identity
                              WHERE exact_identity.company_id = profile.company_id
                                AND exact_identity.profile_id = profile.id
                                AND exact_identity.identity_type = CAST(
                                    :identity_type AS VARCHAR
                                )
                                AND exact_identity.value_hash = CAST(
                                    :identity_hash AS VARCHAR
                                )
                          )
                      )
                  )
                ORDER BY
                    (profile.display_name ILIKE :prefix) DESC,
                    profile.quality_score DESC,
                    profile.updated_at DESC
                LIMIT :limit
                """
            ),
            {
                "company_id": company_id,
                "query": normalized,
                "pattern": f"%{normalized}%",
                "prefix": f"{normalized}%",
                "identity_type": identity_type,
                "identity_hash": identity_hash,
                "limit": limit,
            },
        )
    ).mappings().all()
    return CustomerProfileSearchResponse(
        query_kind=identity_type or "text",
        results=[
            CustomerProfileSearchResult.model_validate(row)
            for row in rows
        ],
    )
