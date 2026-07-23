from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.customer_ingestion_schemas import CustomerIngestionJobCreate
from app.modules.crm.customer_ingestion_service import ingest_customer_records
from app.modules.crm.customer_sync_adapters import get_sync_adapter_definition
from app.modules.crm.customer_sync_schemas import (
    CustomerSyncConnectorCreate,
    CustomerSyncConnectorResponse,
    CustomerSyncExecutionCreate,
    CustomerSyncObservabilityResponse,
    CustomerSyncRunResponse,
)


def secure_fingerprint(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode()).hexdigest()


def retry_delay_seconds(base_seconds: int, attempt: int) -> int:
    exponent = max(0, min(attempt - 1, 10))
    return int(min(base_seconds * (2**exponent), 86_400))


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


def _connector_response(row: Any) -> CustomerSyncConnectorResponse:
    return CustomerSyncConnectorResponse(
        id=row.id,
        source_code=row.source_code,
        source_name=row.source_name,
        adapter_key=row.adapter_key,
        adapter_version=row.adapter_version,
        transport=row.transport,
        status=row.status,
        credential_configured=row.credential_binding_id is not None,
        schedule_minutes=row.schedule_minutes,
        max_attempts=row.max_attempts,
        base_backoff_seconds=row.base_backoff_seconds,
        lease_ttl_seconds=row.lease_ttl_seconds,
        has_cursor=row.cursor is not None,
        cursor_fingerprint=secure_fingerprint(row.cursor),
        next_run_at=row.next_run_at,
        leased_until=row.lease_until,
        consecutive_failures=row.consecutive_failures,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _run_response(row: Any) -> CustomerSyncRunResponse:
    return CustomerSyncRunResponse(
        id=row.id,
        connector_id=row.connector_id,
        ingestion_job_id=row.ingestion_job_id,
        idempotency_key=row.idempotency_key,
        trigger=row.trigger,
        status=row.status,
        attempt=row.attempt,
        cursor_before_fingerprint=secure_fingerprint(row.cursor_before),
        cursor_after_fingerprint=secure_fingerprint(row.cursor_after),
        total_records=row.total_records,
        accepted_records=row.accepted_records,
        rejected_records=row.rejected_records,
        duration_ms=row.duration_ms,
        error_code=row.error_code,
        retry_at=row.retry_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


_CONNECTOR_SELECT = """
    SELECT
        connector.id,
        source.code AS source_code,
        source.name AS source_name,
        connector.adapter_key,
        connector.adapter_version,
        connector.transport,
        connector.status,
        connector.credential_binding_id,
        connector.schedule_minutes,
        connector.max_attempts,
        connector.base_backoff_seconds,
        connector.lease_ttl_seconds,
        connector.cursor,
        connector.next_run_at,
        connector.lease_until,
        connector.consecutive_failures,
        connector.created_at,
        connector.updated_at
    FROM customer_sync_connectors AS connector
    JOIN customer_data_sources AS source ON source.id = connector.source_id
"""

_RUN_SELECT = """
    SELECT
        id,
        connector_id,
        ingestion_job_id,
        idempotency_key,
        trigger,
        status,
        attempt,
        cursor_before,
        cursor_after,
        total_records,
        accepted_records,
        rejected_records,
        duration_ms,
        error_code,
        retry_at,
        started_at,
        completed_at
    FROM customer_sync_runs
"""


async def list_sync_connectors(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> list[CustomerSyncConnectorResponse]:
    rows = (
        await database.execute(
            text(
                f"""
                {_CONNECTOR_SELECT}
                WHERE connector.company_id = :company_id
                ORDER BY connector.created_at DESC
                """
            ),
            {"company_id": company_id},
        )
    ).all()
    return [_connector_response(row) for row in rows]


async def create_sync_connector(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    payload: CustomerSyncConnectorCreate,
) -> CustomerSyncConnectorResponse:
    duplicate = (
        await database.execute(
            text(
                """
                SELECT id
                FROM customer_sync_connectors
                WHERE company_id = :company_id AND source_code = :source_code
                """
            ),
            {"company_id": company_id, "source_code": payload.source_code},
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise ValueError("Já existe um conector com esse código.")

    adapter = get_sync_adapter_definition(payload.adapter_key)
    if adapter is None:
        raise ValueError("O adaptador informado não está registrado.")
    if payload.transport not in adapter.transports:
        raise ValueError("O transporte não é compatível com o adaptador.")

    if payload.credential_binding_id is not None:
        credential = (
            await database.execute(
                text(
                    """
                    SELECT id
                    FROM integration_credentials
                    WHERE company_id = :company_id
                      AND id = :credential_id
                      AND status = 'active'
                    """
                ),
                {
                    "company_id": company_id,
                    "credential_id": payload.credential_binding_id,
                },
            )
        ).scalar_one_or_none()
        if credential is None:
            raise ValueError("A credencial informada não está ativa nesta empresa.")

    source_id = (
        await database.execute(
            text(
                """
                INSERT INTO customer_data_sources (
                    id, company_id, code, name, mode, status
                ) VALUES (
                    gen_random_uuid(), :company_id, :source_code, :source_name,
                    'copied', 'active'
                )
                ON CONFLICT (company_id, code)
                DO UPDATE SET name = EXCLUDED.name, updated_at = now()
                RETURNING id
                """
            ),
            {
                "company_id": company_id,
                "source_code": payload.source_code,
                "source_name": payload.source_name,
            },
        )
    ).scalar_one()

    connector_id = (
        await database.execute(
            text(
                """
                INSERT INTO customer_sync_connectors (
                    id, company_id, source_id, source_code, transport,
                    adapter_key, adapter_version, credential_binding_id, status,
                    schedule_minutes, max_attempts, base_backoff_seconds,
                    lease_ttl_seconds, next_run_at, created_by_user_id
                ) VALUES (
                    gen_random_uuid(), :company_id, :source_id, :source_code,
                    :transport, :adapter_key, :adapter_version,
                    :credential_binding_id, 'active', :schedule_minutes,
                    :max_attempts, :base_backoff_seconds,
                    :lease_ttl_seconds, now(), :actor_user_id
                )
                RETURNING id
                """
            ),
            {
                "company_id": company_id,
                "source_id": source_id,
                "source_code": payload.source_code,
                "transport": payload.transport,
                "adapter_key": payload.adapter_key,
                "adapter_version": adapter.version,
                "credential_binding_id": payload.credential_binding_id,
                "schedule_minutes": payload.schedule_minutes,
                "max_attempts": payload.max_attempts,
                "base_backoff_seconds": payload.base_backoff_seconds,
                "lease_ttl_seconds": payload.lease_ttl_seconds,
                "actor_user_id": actor_user_id,
            },
        )
    ).scalar_one()
    row = (
        await database.execute(
            text(
                f"""
                {_CONNECTOR_SELECT}
                WHERE connector.company_id = :company_id
                  AND connector.id = :connector_id
                """
            ),
            {"company_id": company_id, "connector_id": connector_id},
        )
    ).one()
    await _governance_event(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        event_type="customer.sync_connector.created",
        subject_type="sync_connector",
        subject_id=connector_id,
        payload={
            "source_code": payload.source_code,
            "transport": payload.transport,
            "adapter_key": payload.adapter_key,
            "credential_configured": payload.credential_binding_id is not None,
        },
    )
    return _connector_response(row)


async def set_sync_connector_status(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    connector_id: UUID,
    target_status: str,
) -> CustomerSyncConnectorResponse:
    if target_status not in {"active", "paused"}:
        raise ValueError("Status de conector inválido.")
    updated = (
        await database.execute(
            text(
                """
                UPDATE customer_sync_connectors
                SET
                    status = CAST(:target_status AS varchar),
                    next_run_at = CASE
                        WHEN CAST(:target_status AS varchar) = 'active' THEN now()
                        ELSE next_run_at
                    END,
                    updated_at = now()
                WHERE company_id = :company_id AND id = :connector_id
                RETURNING id
                """
            ),
            {
                "company_id": company_id,
                "connector_id": connector_id,
                "target_status": target_status,
            },
        )
    ).scalar_one_or_none()
    if updated is None:
        raise LookupError("Conector de sincronização não encontrado.")
    row = (
        await database.execute(
            text(
                f"""
                {_CONNECTOR_SELECT}
                WHERE connector.company_id = :company_id
                  AND connector.id = :connector_id
                """
            ),
            {"company_id": company_id, "connector_id": connector_id},
        )
    ).one()
    await _governance_event(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        event_type=f"customer.sync_connector.{target_status}",
        subject_type="sync_connector",
        subject_id=connector_id,
        payload={"status": target_status},
    )
    return _connector_response(row)


async def list_sync_runs(
    database: AsyncSession,
    *,
    company_id: UUID,
    limit: int = 50,
) -> list[CustomerSyncRunResponse]:
    rows = (
        await database.execute(
            text(
                f"""
                {_RUN_SELECT}
                WHERE company_id = :company_id
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"company_id": company_id, "limit": limit},
        )
    ).all()
    return [_run_response(row) for row in rows]


async def execute_customer_sync(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    connector_id: UUID,
    payload: CustomerSyncExecutionCreate,
) -> CustomerSyncRunResponse:
    existing = (
        await database.execute(
            text(
                f"""
                {_RUN_SELECT}
                WHERE company_id = :company_id
                  AND connector_id = :connector_id
                  AND idempotency_key = :idempotency_key
                """
            ),
            {
                "company_id": company_id,
                "connector_id": connector_id,
                "idempotency_key": payload.idempotency_key,
            },
        )
    ).one_or_none()
    if existing is not None:
        return _run_response(existing)

    connector = (
        await database.execute(
            text(
                """
                SELECT
                    connector.id,
                    connector.source_code,
                    source.name AS source_name,
                    connector.status,
                    connector.cursor,
                    connector.schedule_minutes,
                    connector.max_attempts,
                    connector.base_backoff_seconds,
                    connector.lease_ttl_seconds,
                    connector.consecutive_failures
                FROM customer_sync_connectors AS connector
                JOIN customer_data_sources AS source ON source.id = connector.source_id
                WHERE connector.company_id = :company_id
                  AND connector.id = :connector_id
                """
            ),
            {"company_id": company_id, "connector_id": connector_id},
        )
    ).one_or_none()
    if connector is None:
        raise LookupError("Conector de sincronização não encontrado.")
    if connector.status != "active":
        raise ValueError("O conector está pausado.")

    lease_token = secrets.token_urlsafe(32)
    lease_hash = secure_fingerprint(lease_token)
    claimed = (
        await database.execute(
            text(
                """
                UPDATE customer_sync_connectors
                SET
                    lease_token_hash = :lease_hash,
                    lease_until = now() + (:lease_ttl_seconds * interval '1 second'),
                    updated_at = now()
                WHERE company_id = :company_id
                  AND id = :connector_id
                  AND status = 'active'
                  AND (lease_until IS NULL OR lease_until <= now())
                RETURNING id
                """
            ),
            {
                "company_id": company_id,
                "connector_id": connector_id,
                "lease_hash": lease_hash,
                "lease_ttl_seconds": connector.lease_ttl_seconds,
            },
        )
    ).scalar_one_or_none()
    if claimed is None:
        raise ValueError("Já existe uma sincronização em andamento para este conector.")

    attempt = min(connector.consecutive_failures + 1, connector.max_attempts)
    run_id = (
        await database.execute(
            text(
                """
                INSERT INTO customer_sync_runs (
                    id, company_id, connector_id, idempotency_key, trigger, status,
                    attempt, lease_fingerprint, cursor_before, started_at
                ) VALUES (
                    gen_random_uuid(), :company_id, :connector_id, :idempotency_key,
                    :trigger, 'running', :attempt, :lease_hash, :cursor_before, now()
                )
                RETURNING id
                """
            ),
            {
                "company_id": company_id,
                "connector_id": connector_id,
                "idempotency_key": payload.idempotency_key,
                "trigger": payload.trigger,
                "attempt": attempt,
                "lease_hash": lease_hash,
                "cursor_before": connector.cursor,
            },
        )
    ).scalar_one()

    ingestion_key = (
        "sync-" + hashlib.sha256(f"{connector_id}:{payload.idempotency_key}".encode()).hexdigest()
    )
    try:
        ingestion = await ingest_customer_records(
            database,
            company_id=company_id,
            actor_user_id=actor_user_id,
            payload=CustomerIngestionJobCreate(
                source_code=connector.source_code,
                source_name=connector.source_name,
                mode="incremental",
                idempotency_key=ingestion_key,
                cursor=connector.cursor,
                records=payload.records,
            ),
        )
    except ValueError:
        failures = connector.consecutive_failures + 1
        delay = retry_delay_seconds(connector.base_backoff_seconds, failures)
        retry_at = datetime.now(UTC) + timedelta(seconds=delay)
        await database.execute(
            text(
                """
                UPDATE customer_sync_runs
                SET
                    status = 'failed',
                    error_code = 'SYNC_INPUT_REJECTED',
                    retry_at = :retry_at,
                    completed_at = now(),
                    duration_ms = GREATEST(
                        0,
                        (EXTRACT(EPOCH FROM (now() - started_at)) * 1000)::integer
                    )
                WHERE company_id = :company_id AND id = :run_id
                """
            ),
            {"company_id": company_id, "run_id": run_id, "retry_at": retry_at},
        )
        await database.execute(
            text(
                """
                UPDATE customer_sync_connectors
                SET
                    consecutive_failures = consecutive_failures + 1,
                    next_run_at = :retry_at,
                    lease_token_hash = NULL,
                    lease_until = NULL,
                    updated_at = now()
                WHERE company_id = :company_id
                  AND id = :connector_id
                  AND lease_token_hash = :lease_hash
                """
            ),
            {
                "company_id": company_id,
                "connector_id": connector_id,
                "lease_hash": lease_hash,
                "retry_at": retry_at,
            },
        )
        await _governance_event(
            database,
            company_id=company_id,
            actor_user_id=actor_user_id,
            event_type="customer.sync.failed",
            subject_type="sync_run",
            subject_id=run_id,
            payload={"error_code": "SYNC_INPUT_REJECTED", "retry_delay_seconds": delay},
        )
    else:
        run_status = "completed" if ingestion.status == "completed" else "partial"
        await database.execute(
            text(
                """
                UPDATE customer_sync_runs
                SET
                    ingestion_job_id = :ingestion_job_id,
                    status = CAST(:run_status AS varchar),
                    cursor_after = :cursor_after,
                    total_records = :total_records,
                    accepted_records = :accepted_records,
                    rejected_records = :rejected_records,
                    completed_at = now(),
                    duration_ms = GREATEST(
                        0,
                        (EXTRACT(EPOCH FROM (now() - started_at)) * 1000)::integer
                    )
                WHERE company_id = :company_id AND id = :run_id
                """
            ),
            {
                "company_id": company_id,
                "run_id": run_id,
                "ingestion_job_id": ingestion.id,
                "run_status": run_status,
                "cursor_after": payload.cursor_after,
                "total_records": ingestion.total_records,
                "accepted_records": ingestion.accepted_records,
                "rejected_records": ingestion.rejected_records,
            },
        )
        await database.execute(
            text(
                """
                UPDATE customer_sync_connectors
                SET
                    cursor = COALESCE(:cursor_after, cursor),
                    consecutive_failures = 0,
                    next_run_at = now() + (:schedule_minutes * interval '1 minute'),
                    lease_token_hash = NULL,
                    lease_until = NULL,
                    updated_at = now()
                WHERE company_id = :company_id
                  AND id = :connector_id
                  AND lease_token_hash = :lease_hash
                """
            ),
            {
                "company_id": company_id,
                "connector_id": connector_id,
                "cursor_after": payload.cursor_after,
                "schedule_minutes": connector.schedule_minutes,
                "lease_hash": lease_hash,
            },
        )
        await _governance_event(
            database,
            company_id=company_id,
            actor_user_id=actor_user_id,
            event_type="customer.sync.completed",
            subject_type="sync_run",
            subject_id=run_id,
            payload={
                "status": run_status,
                "accepted_records": ingestion.accepted_records,
                "rejected_records": ingestion.rejected_records,
            },
        )

    row = (
        await database.execute(
            text(
                f"""
                {_RUN_SELECT}
                WHERE company_id = :company_id AND id = :run_id
                """
            ),
            {"company_id": company_id, "run_id": run_id},
        )
    ).one()
    return _run_response(row)


async def get_sync_observability(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> CustomerSyncObservabilityResponse:
    row = (
        await database.execute(
            text(
                """
                SELECT
                    COUNT(*)::integer AS connectors_total,
                    COUNT(*) FILTER (WHERE status = 'active')::integer AS connectors_active,
                    COUNT(*) FILTER (
                        WHERE status = 'active'
                          AND next_run_at IS NOT NULL
                          AND next_run_at <= now()
                    )::integer AS connectors_due,
                    COUNT(*) FILTER (
                        WHERE lease_until IS NOT NULL AND lease_until > now()
                    )::integer AS connectors_leased,
                    COALESCE((
                        SELECT COUNT(*)::integer
                        FROM customer_sync_runs
                        WHERE company_id = :company_id
                    ), 0) AS runs_total,
                    COALESCE((
                        SELECT COUNT(*) FILTER (WHERE status = 'failed')::integer
                        FROM customer_sync_runs
                        WHERE company_id = :company_id
                    ), 0) AS runs_failed,
                    COALESCE((
                        SELECT SUM(total_records)::integer
                        FROM customer_sync_runs
                        WHERE company_id = :company_id
                    ), 0) AS records_processed,
                    COALESCE((
                        SELECT SUM(rejected_records)::integer
                        FROM customer_sync_runs
                        WHERE company_id = :company_id
                    ), 0) AS records_rejected,
                    COALESCE((
                        SELECT ROUND(
                            100.0 * COUNT(*) FILTER (
                                WHERE status IN ('completed', 'partial')
                            ) / NULLIF(COUNT(*), 0),
                            2
                        )::float
                        FROM customer_sync_runs
                        WHERE company_id = :company_id
                    ), 0.0) AS success_rate,
                    COALESCE((
                        SELECT AVG(duration_ms)::integer
                        FROM customer_sync_runs
                        WHERE company_id = :company_id AND duration_ms IS NOT NULL
                    ), 0) AS average_duration_ms
                FROM customer_sync_connectors
                WHERE company_id = :company_id
                """
            ),
            {"company_id": company_id},
        )
    ).one()
    return CustomerSyncObservabilityResponse(**row._mapping)
