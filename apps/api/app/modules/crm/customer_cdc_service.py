from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.customer_cdc_schemas import (
    CustomerCdcAcknowledgeRequest,
    CustomerCdcCheckpointResponse,
    CustomerCdcEventPage,
    CustomerCdcRetentionPreviewResponse,
    CustomerCdcRetentionPurgeRequest,
    CustomerCdcRetentionPurgeResponse,
    CustomerCdcSubscriptionCreate,
    CustomerCdcSubscriptionResponse,
    CustomerCdcSummaryResponse,
    CustomerChangeEventResponse,
    CustomerChangeOperation,
)

_ALLOWED_CHANGED_FIELDS = frozenset(
    {
        "display_name",
        "email",
        "external_id",
        "phone",
        "quality_score",
    }
)


def customer_change_metadata(record: Mapping[str, Any]) -> tuple[list[str], str]:
    changed_fields = sorted(
        field
        for field in _ALLOWED_CHANGED_FIELDS
        if record.get(field) not in (None, "")
    )
    canonical_payload = json.dumps(
        dict(record),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )
    fingerprint = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    return changed_fields, fingerprint


def _masked_fingerprint(value: str) -> str:
    return f"{value[:12]}..."


def _subscription_from_row(row: RowMapping) -> CustomerCdcSubscriptionResponse:
    return CustomerCdcSubscriptionResponse(
        id=row["id"],
        name=row["name"],
        consumer_key=row["consumer_key"],
        status=row["status"],
        operations=list(row["operations"]),
        batch_size=row["batch_size"],
        retention_days=row["retention_days"],
        last_acknowledged_sequence=row["last_acknowledged_sequence"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _event_from_row(row: RowMapping) -> CustomerChangeEventResponse:
    return CustomerChangeEventResponse(
        id=row["id"],
        sequence_number=row["sequence_number"],
        profile_id=row["profile_id"],
        operation=row["operation"],
        changed_fields=list(row["changed_fields"]),
        payload_fingerprint=_masked_fingerprint(row["payload_fingerprint"]),
        occurred_at=row["occurred_at"],
    )


async def record_customer_change(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID | None,
    profile_id: UUID | None,
    source_id: UUID | None,
    ingestion_job_id: UUID | None,
    operation: CustomerChangeOperation,
    record: Mapping[str, Any],
) -> UUID | None:
    changed_fields, payload_fingerprint = customer_change_metadata(record)
    source_record_fingerprint = hashlib.sha256(
        str(record.get("external_id") or payload_fingerprint).encode("utf-8")
    ).hexdigest()

    duplicate = (
        await database.execute(
            text(
                """
                SELECT id
                FROM customer_change_events
                WHERE company_id = :company_id
                  AND source_id IS NOT DISTINCT FROM :source_id
                  AND profile_id IS NOT DISTINCT FROM :profile_id
                  AND payload_fingerprint = :payload_fingerprint
                LIMIT 1
                """
            ),
            {
                "company_id": company_id,
                "source_id": source_id,
                "profile_id": profile_id,
                "payload_fingerprint": payload_fingerprint,
            },
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        return None

    sequence_number = (
        await database.execute(
            text(
                """
                INSERT INTO customer_cdc_counters (company_id, next_sequence)
                VALUES (:company_id, 2)
                ON CONFLICT (company_id)
                DO UPDATE SET next_sequence = customer_cdc_counters.next_sequence + 1
                RETURNING next_sequence - 1
                """
            ),
            {"company_id": company_id},
        )
    ).scalar_one()

    event_id = uuid4()
    await database.execute(
        text(
            """
            INSERT INTO customer_change_events (
                id,
                company_id,
                sequence_number,
                profile_id,
                operation,
                changed_fields,
                source_id,
                ingestion_job_id,
                source_record_fingerprint,
                payload_fingerprint,
                actor_user_id,
                occurred_at
            )
            VALUES (
                :id,
                :company_id,
                :sequence_number,
                :profile_id,
                :operation,
                CAST(:changed_fields AS jsonb),
                :source_id,
                :ingestion_job_id,
                :source_record_fingerprint,
                :payload_fingerprint,
                :actor_user_id,
                now()
            )
            """
        ),
        {
            "id": event_id,
            "company_id": company_id,
            "sequence_number": sequence_number,
            "profile_id": profile_id,
            "operation": operation,
            "changed_fields": json.dumps(changed_fields),
            "source_id": source_id,
            "ingestion_job_id": ingestion_job_id,
            "source_record_fingerprint": source_record_fingerprint,
            "payload_fingerprint": payload_fingerprint,
            "actor_user_id": actor_user_id,
        },
    )
    return event_id


async def create_customer_cdc_subscription(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    payload: CustomerCdcSubscriptionCreate,
) -> CustomerCdcSubscriptionResponse:
    subscription_id = uuid4()
    try:
        row = (
            (
                await database.execute(
                    text(
                        """
                        INSERT INTO customer_cdc_subscriptions (
                            id,
                            company_id,
                            name,
                            consumer_key,
                            status,
                            operations,
                            batch_size,
                            retention_days,
                            last_acknowledged_sequence,
                            created_by_user_id,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            :id,
                            :company_id,
                            :name,
                            :consumer_key,
                            'active',
                            CAST(:operations AS jsonb),
                            :batch_size,
                            :retention_days,
                            0,
                            :actor_user_id,
                            now(),
                            now()
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "id": subscription_id,
                        "company_id": company_id,
                        "name": payload.name.strip(),
                        "consumer_key": payload.consumer_key,
                        "operations": json.dumps(payload.operations),
                        "batch_size": payload.batch_size,
                        "retention_days": payload.retention_days,
                        "actor_user_id": actor_user_id,
                    },
                )
            )
            .mappings()
            .one()
        )
    except Exception as exc:
        if "customer_cdc_subscriptions_company_consumer_key_key" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ja existe um consumidor CDC com esta chave.",
            ) from exc
        raise
    return _subscription_from_row(row)


async def list_customer_cdc_subscriptions(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> list[CustomerCdcSubscriptionResponse]:
    rows = (
        (
            await database.execute(
                text(
                    """
                    SELECT *
                    FROM customer_cdc_subscriptions
                    WHERE company_id = :company_id
                    ORDER BY created_at DESC
                    """
                ),
                {"company_id": company_id},
            )
        )
        .mappings()
        .all()
    )
    return [_subscription_from_row(row) for row in rows]


async def set_customer_cdc_subscription_status(
    database: AsyncSession,
    *,
    company_id: UUID,
    subscription_id: UUID,
    target_status: str,
) -> CustomerCdcSubscriptionResponse:
    row = (
        (
            await database.execute(
                text(
                    """
                    UPDATE customer_cdc_subscriptions
                    SET status = :target_status,
                        updated_at = now()
                    WHERE id = :subscription_id
                      AND company_id = :company_id
                    RETURNING *
                    """
                ),
                {
                    "company_id": company_id,
                    "subscription_id": subscription_id,
                    "target_status": target_status,
                },
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assinatura CDC nao encontrada.",
        )
    return _subscription_from_row(row)


async def list_customer_change_events(
    database: AsyncSession,
    *,
    company_id: UUID,
    after_sequence: int,
    limit: int,
    subscription_id: UUID | None = None,
) -> CustomerCdcEventPage:
    last_acknowledged_sequence: int | None = None
    operations: list[str] | None = None
    effective_limit = limit
    if subscription_id is not None:
        subscription = (
            (
                await database.execute(
                    text(
                        """
                        SELECT status, operations, batch_size, last_acknowledged_sequence
                        FROM customer_cdc_subscriptions
                        WHERE id = :subscription_id
                          AND company_id = :company_id
                        """
                    ),
                    {
                        "company_id": company_id,
                        "subscription_id": subscription_id,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if subscription is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assinatura CDC nao encontrada.",
            )
        if subscription["status"] != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A assinatura CDC esta pausada.",
            )
        last_acknowledged_sequence = subscription["last_acknowledged_sequence"]
        after_sequence = max(after_sequence, last_acknowledged_sequence)
        operations = list(subscription["operations"])
        effective_limit = min(limit, subscription["batch_size"])

    parameters: dict[str, Any] = {
        "company_id": company_id,
        "after_sequence": after_sequence,
        "limit": effective_limit,
        "filter_operations": operations is not None,
        "operations": operations or [],
    }

    rows = (
        (
            await database.execute(
                text(
                    """
                    SELECT
                        id,
                        sequence_number,
                        profile_id,
                        operation,
                        changed_fields,
                        payload_fingerprint,
                        occurred_at
                    FROM customer_change_events
                    WHERE company_id = :company_id
                      AND sequence_number > :after_sequence
                      AND (
                          :filter_operations = false
                          OR operation = ANY(CAST(:operations AS text[]))
                      )
                    ORDER BY sequence_number
                    LIMIT :limit
                    """
                ),
                parameters,
            )
        )
        .mappings()
        .all()
    )
    items = [_event_from_row(row) for row in rows]
    return CustomerCdcEventPage(
        items=items,
        next_sequence=items[-1].sequence_number if items else None,
        last_acknowledged_sequence=last_acknowledged_sequence,
    )


async def acknowledge_customer_cdc_checkpoint(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    subscription_id: UUID,
    payload: CustomerCdcAcknowledgeRequest,
) -> CustomerCdcCheckpointResponse:
    subscription = (
        (
            await database.execute(
                text(
                    """
                    SELECT id, status, last_acknowledged_sequence
                    FROM customer_cdc_subscriptions
                    WHERE id = :subscription_id
                      AND company_id = :company_id
                    FOR UPDATE
                    """
                ),
                {
                    "company_id": company_id,
                    "subscription_id": subscription_id,
                },
            )
        )
        .mappings()
        .one_or_none()
    )
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assinatura CDC nao encontrada.",
        )
    if subscription["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A assinatura CDC esta pausada.",
        )

    previous_sequence = subscription["last_acknowledged_sequence"]
    if payload.through_sequence <= previous_sequence:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O checkpoint deve avancar de forma estritamente crescente.",
        )

    latest_sequence = (
        await database.execute(
            text(
                """
                SELECT COALESCE(MAX(sequence_number), 0)
                FROM customer_change_events
                WHERE company_id = :company_id
                """
            ),
            {"company_id": company_id},
        )
    ).scalar_one()
    if payload.through_sequence > latest_sequence:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O checkpoint nao pode ultrapassar o ultimo evento disponivel.",
        )

    acknowledged_at = datetime.now(UTC)
    await database.execute(
        text(
            """
            UPDATE customer_cdc_subscriptions
            SET last_acknowledged_sequence = :through_sequence,
                updated_at = :acknowledged_at
            WHERE id = :subscription_id
              AND company_id = :company_id
            """
        ),
        {
            "company_id": company_id,
            "subscription_id": subscription_id,
            "through_sequence": payload.through_sequence,
            "acknowledged_at": acknowledged_at,
        },
    )
    await database.execute(
        text(
            """
            INSERT INTO customer_cdc_checkpoint_history (
                id,
                company_id,
                subscription_id,
                previous_sequence,
                acknowledged_sequence,
                acknowledged_by_user_id,
                acknowledged_at
            )
            VALUES (
                :id,
                :company_id,
                :subscription_id,
                :previous_sequence,
                :acknowledged_sequence,
                :actor_user_id,
                :acknowledged_at
            )
            """
        ),
        {
            "id": uuid4(),
            "company_id": company_id,
            "subscription_id": subscription_id,
            "previous_sequence": previous_sequence,
            "acknowledged_sequence": payload.through_sequence,
            "actor_user_id": actor_user_id,
            "acknowledged_at": acknowledged_at,
        },
    )
    return CustomerCdcCheckpointResponse(
        subscription_id=subscription_id,
        previous_sequence=previous_sequence,
        acknowledged_sequence=payload.through_sequence,
        acknowledged_at=acknowledged_at,
    )


async def get_customer_cdc_summary(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> CustomerCdcSummaryResponse:
    row = (
        (
            await database.execute(
                text(
                    """
                    SELECT
                        COALESCE(
                            (
                                SELECT MAX(sequence_number)
                                FROM customer_change_events
                                WHERE company_id = :company_id
                            ),
                            0
                        ) AS latest_sequence,
                        (
                            SELECT COUNT(*)
                            FROM customer_change_events
                            WHERE company_id = :company_id
                        ) AS retained_events,
                        COUNT(*) FILTER (WHERE status = 'active') AS active_subscriptions,
                        COUNT(*) FILTER (WHERE status = 'paused') AS paused_subscriptions,
                        COALESCE(
                            MAX(
                                GREATEST(
                                    (
                                        SELECT COALESCE(MAX(sequence_number), 0)
                                        FROM customer_change_events
                                        WHERE company_id = :company_id
                                    ) - last_acknowledged_sequence,
                                    0
                                )
                            ),
                            0
                        ) AS maximum_lag
                    FROM customer_cdc_subscriptions
                    WHERE company_id = :company_id
                    """
                ),
                {"company_id": company_id},
            )
        )
        .mappings()
        .one()
    )
    return CustomerCdcSummaryResponse(**row)


async def preview_customer_cdc_retention(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> CustomerCdcRetentionPreviewResponse:
    row = (
        (
            await database.execute(
                text(
                    """
                    WITH policy AS (
                        SELECT
                            COUNT(*) FILTER (WHERE status = 'active') AS active_count,
                            COALESCE(
                                MIN(last_acknowledged_sequence)
                                    FILTER (WHERE status = 'active'),
                                0
                            ) AS cutoff_sequence,
                            COALESCE(
                                MAX(retention_days) FILTER (WHERE status = 'active'),
                                0
                            ) AS retention_days
                        FROM customer_cdc_subscriptions
                        WHERE company_id = :company_id
                    )
                    SELECT
                        policy.active_count AS active_subscriptions,
                        policy.cutoff_sequence,
                        policy.retention_days AS effective_retention_days,
                        COUNT(event.id) FILTER (
                            WHERE policy.active_count > 0
                              AND event.sequence_number <= policy.cutoff_sequence
                              AND event.occurred_at < (
                                  now() - make_interval(days => policy.retention_days)
                              )
                        ) AS eligible_events,
                        COUNT(event.id) FILTER (
                            WHERE NOT (
                                policy.active_count > 0
                                AND event.sequence_number <= policy.cutoff_sequence
                                AND event.occurred_at < (
                                    now() - make_interval(days => policy.retention_days)
                                )
                            )
                        ) AS protected_events
                    FROM policy
                    LEFT JOIN customer_change_events AS event
                      ON event.company_id = :company_id
                    GROUP BY
                        policy.active_count,
                        policy.cutoff_sequence,
                        policy.retention_days
                    """
                ),
                {"company_id": company_id},
            )
        )
        .mappings()
        .one()
    )
    active_subscriptions = int(row["active_subscriptions"])
    eligible_events = int(row["eligible_events"] or 0)
    if active_subscriptions == 0:
        reason = "Nenhum evento pode ser removido sem consumidor ativo."
    elif eligible_events == 0:
        reason = "Nenhum evento reconhecido ultrapassou o prazo de retencao."
    else:
        reason = "Somente eventos reconhecidos por todos e vencidos serao removidos."
    return CustomerCdcRetentionPreviewResponse(
        active_subscriptions=active_subscriptions,
        cutoff_sequence=int(row["cutoff_sequence"]),
        effective_retention_days=int(row["effective_retention_days"]),
        eligible_events=eligible_events,
        protected_events=int(row["protected_events"] or 0),
        reason=reason,
    )


async def purge_expired_customer_cdc_events(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID | None,
    payload: CustomerCdcRetentionPurgeRequest,
    execution_source: str = "manual",
) -> CustomerCdcRetentionPurgeResponse:
    await database.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:company_key, 0))"),
        {"company_key": str(company_id)},
    )
    preview = await preview_customer_cdc_retention(database, company_id=company_id)
    run_id = uuid4()
    executed_at = datetime.now(UTC)
    deleted_events = 0

    if preview.active_subscriptions > 0 and preview.eligible_events > 0:
        deleted_events = int(
            (
                await database.execute(
                    text(
                        """
                        WITH candidates AS (
                            SELECT id
                            FROM customer_change_events
                            WHERE company_id = :company_id
                              AND sequence_number <= :cutoff_sequence
                              AND occurred_at < (
                                  now() - make_interval(days => :retention_days)
                              )
                            ORDER BY sequence_number
                            LIMIT :max_delete
                            FOR UPDATE SKIP LOCKED
                        ),
                        removed AS (
                            DELETE FROM customer_change_events AS event
                            USING candidates
                            WHERE event.id = candidates.id
                              AND event.company_id = :company_id
                            RETURNING event.id
                        )
                        SELECT COUNT(*) FROM removed
                        """
                    ),
                    {
                        "company_id": company_id,
                        "cutoff_sequence": preview.cutoff_sequence,
                        "retention_days": preview.effective_retention_days,
                        "max_delete": payload.max_delete,
                    },
                )
            ).scalar_one()
        )

    await database.execute(
        text(
            """
            INSERT INTO customer_cdc_retention_runs (
                id,
                company_id,
                cutoff_sequence,
                effective_retention_days,
                eligible_events,
                deleted_events,
                max_delete,
                executed_by_user_id,
                execution_source,
                executed_at
            )
            VALUES (
                :id,
                :company_id,
                :cutoff_sequence,
                :effective_retention_days,
                :eligible_events,
                :deleted_events,
                :max_delete,
                :actor_user_id,
                :execution_source,
                :executed_at
            )
            """
        ),
        {
            "id": run_id,
            "company_id": company_id,
            "cutoff_sequence": preview.cutoff_sequence,
            "effective_retention_days": preview.effective_retention_days,
            "eligible_events": preview.eligible_events,
            "deleted_events": deleted_events,
            "max_delete": payload.max_delete,
            "actor_user_id": actor_user_id,
            "execution_source": execution_source,
            "executed_at": executed_at,
        },
    )
    return CustomerCdcRetentionPurgeResponse(
        run_id=run_id,
        cutoff_sequence=preview.cutoff_sequence,
        effective_retention_days=preview.effective_retention_days,
        deleted_events=deleted_events,
        executed_at=executed_at,
    )
