from __future__ import annotations

import asyncio
import hashlib
import json
import socket
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.resources import create_resources
from app.modules.crm.customer_sync_adapters import (
    AdapterReadiness,
    evaluate_adapter_readiness,
    get_sync_adapter_definition,
    list_sync_adapter_definitions,
)
from app.modules.crm.customer_sync_scheduler_schemas import (
    CustomerSyncAdapterHealthResponse,
    CustomerSyncAdapterResponse,
    CustomerSyncCredentialOptionResponse,
    CustomerSyncDispatchResponse,
    CustomerSyncSchedulerSummary,
)


@dataclass(frozen=True, slots=True)
class SchedulerResult:
    companies: int
    evaluated: int
    dispatched: int
    blocked: int


def _worker_fingerprint(worker_id: str) -> str:
    return hashlib.sha256(worker_id.encode()).hexdigest()


def adapter_catalog() -> list[CustomerSyncAdapterResponse]:
    return [
        CustomerSyncAdapterResponse(
            key=definition.key,
            version=definition.version,
            name=definition.name,
            description=definition.description,
            transports=list(definition.transports),
            requires_credential=definition.requires_credential,
            supports_scheduled_dispatch=definition.supports_scheduled_dispatch,
        )
        for definition in list_sync_adapter_definitions()
    ]


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


def _health_response(row: Any) -> CustomerSyncAdapterHealthResponse:
    return CustomerSyncAdapterHealthResponse(
        id=row.id,
        connector_id=row.connector_id,
        adapter_key=row.adapter_key,
        adapter_version=row.adapter_version,
        status=row.status,
        error_code=row.error_code,
        latency_ms=row.latency_ms,
        checked_at=row.checked_at,
    )


def _dispatch_response(row: Any) -> CustomerSyncDispatchResponse:
    return CustomerSyncDispatchResponse(
        id=row.id,
        connector_id=row.connector_id,
        adapter_key=row.adapter_key,
        adapter_version=row.adapter_version,
        schedule_slot=row.schedule_slot,
        status=row.status,
        attempts=row.attempts,
        available_at=row.available_at,
        error_code=row.error_code,
        response_status_code=row.response_status_code,
        response_bytes=row.response_bytes,
        records_received=row.records_received,
        has_result_fingerprint=row.result_fingerprint is not None,
        created_at=row.created_at,
        claimed_at=row.claimed_at,
        claim_expires_at=row.claim_expires_at,
        completed_at=row.completed_at,
    )


async def _connector_probe_state(
    database: AsyncSession,
    *,
    company_id: UUID,
    connector_id: UUID,
) -> Any:
    return (
        await database.execute(
            text(
                """
                SELECT
                    connector.id,
                    connector.adapter_key,
                    connector.adapter_version,
                    connector.transport,
                    connector.credential_binding_id,
                    connector.created_by_user_id,
                    connection.success AS connection_test_success,
                    COALESCE(connection.duration_ms, 0) AS connection_duration_ms
                FROM customer_sync_connectors AS connector
                LEFT JOIN LATERAL (
                    SELECT test.success, test.duration_ms
                    FROM plugin_connection_tests AS test
                    WHERE test.company_id = connector.company_id
                      AND test.credential_id = connector.credential_binding_id
                    ORDER BY test.created_at DESC
                    LIMIT 1
                ) AS connection ON true
                WHERE connector.company_id = :company_id
                  AND connector.id = :connector_id
                """
            ),
            {"company_id": company_id, "connector_id": connector_id},
        )
    ).one_or_none()


async def _record_health(
    database: AsyncSession,
    *,
    company_id: UUID,
    connector: Any,
    readiness: AdapterReadiness,
) -> CustomerSyncAdapterHealthResponse:
    row = (
        await database.execute(
            text(
                """
                INSERT INTO customer_sync_adapter_health_checks (
                    id, company_id, connector_id, adapter_key, adapter_version,
                    status, error_code, latency_ms
                ) VALUES (
                    gen_random_uuid(), :company_id, :connector_id, :adapter_key,
                    :adapter_version, :status, :error_code, :latency_ms
                )
                RETURNING
                    id, connector_id, adapter_key, adapter_version, status,
                    error_code, latency_ms, checked_at
                """
            ),
            {
                "company_id": company_id,
                "connector_id": connector.id,
                "adapter_key": connector.adapter_key,
                "adapter_version": connector.adapter_version,
                "status": readiness.status,
                "error_code": readiness.error_code,
                "latency_ms": connector.connection_duration_ms,
            },
        )
    ).one()
    return _health_response(row)


async def probe_sync_connector_health(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    connector_id: UUID,
) -> CustomerSyncAdapterHealthResponse:
    connector = await _connector_probe_state(
        database,
        company_id=company_id,
        connector_id=connector_id,
    )
    if connector is None:
        raise LookupError("Conector de sincronização não encontrado.")
    readiness = evaluate_adapter_readiness(
        adapter_key=connector.adapter_key,
        transport=connector.transport,
        credential_configured=connector.credential_binding_id is not None,
        connection_test_success=connector.connection_test_success,
    )
    response = await _record_health(
        database,
        company_id=company_id,
        connector=connector,
        readiness=readiness,
    )
    await _governance_event(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        event_type="customer.sync_adapter.health_checked",
        subject_type="sync_connector",
        subject_id=connector_id,
        payload={"status": response.status, "error_code": response.error_code},
    )
    return response


async def list_sync_adapter_health(
    database: AsyncSession,
    *,
    company_id: UUID,
    limit: int = 100,
) -> list[CustomerSyncAdapterHealthResponse]:
    rows = (
        await database.execute(
            text(
                """
                SELECT
                    id, connector_id, adapter_key, adapter_version, status,
                    error_code, latency_ms, checked_at
                FROM customer_sync_adapter_health_checks
                WHERE company_id = :company_id
                ORDER BY checked_at DESC
                LIMIT :limit
                """
            ),
            {"company_id": company_id, "limit": limit},
        )
    ).all()
    return [_health_response(row) for row in rows]


async def list_sync_dispatches(
    database: AsyncSession,
    *,
    company_id: UUID,
    limit: int = 100,
) -> list[CustomerSyncDispatchResponse]:
    rows = (
        await database.execute(
            text(
                """
                SELECT
                    id, connector_id, adapter_key, adapter_version, schedule_slot,
                    status, attempts, available_at, error_code, created_at,
                    response_status_code, response_bytes, records_received,
                    result_fingerprint, claimed_at, claim_expires_at, completed_at
                FROM customer_sync_dispatches
                WHERE company_id = :company_id
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"company_id": company_id, "limit": limit},
        )
    ).all()
    return [_dispatch_response(row) for row in rows]


async def sync_scheduler_summary(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> CustomerSyncSchedulerSummary:
    row = (
        await database.execute(
            text(
                """
                WITH latest_health AS (
                    SELECT DISTINCT ON (connector_id) connector_id, status
                    FROM customer_sync_adapter_health_checks
                    WHERE company_id = :company_id
                    ORDER BY connector_id, checked_at DESC
                )
                SELECT
                    COALESCE((
                        SELECT COUNT(*) FILTER (WHERE status = 'ready')::integer
                        FROM latest_health
                    ), 0) AS health_ready,
                    COALESCE((
                        SELECT COUNT(*) FILTER (WHERE status = 'unverified')::integer
                        FROM latest_health
                    ), 0) AS health_unverified,
                    COALESCE((
                        SELECT COUNT(*) FILTER (WHERE status = 'degraded')::integer
                        FROM latest_health
                    ), 0) AS health_degraded,
                    COALESCE((
                        SELECT COUNT(*) FILTER (WHERE status = 'blocked')::integer
                        FROM latest_health
                    ), 0) AS health_blocked,
                    COUNT(*) FILTER (WHERE status = 'pending')::integer AS dispatch_pending,
                    COUNT(*) FILTER (WHERE status = 'claimed')::integer AS dispatch_claimed,
                    COUNT(*) FILTER (WHERE status = 'failed')::integer AS dispatch_failed,
                    COUNT(*) FILTER (
                        WHERE status = 'dead_letter'
                    )::integer AS dispatch_dead_letter,
                    MIN(created_at) FILTER (WHERE status = 'pending') AS oldest_pending_at
                FROM customer_sync_dispatches
                WHERE company_id = :company_id
                """
            ),
            {"company_id": company_id},
        )
    ).one()
    return CustomerSyncSchedulerSummary(**row._mapping)


async def list_sync_credential_options(
    database: AsyncSession,
    *,
    company_id: UUID,
) -> list[CustomerSyncCredentialOptionResponse]:
    rows = (
        await database.execute(
            text(
                """
                SELECT
                    credential.id,
                    credential.name,
                    plugin.code AS plugin_code,
                    plugin.name AS plugin_name,
                    credential.expires_at
                FROM integration_credentials AS credential
                JOIN plugins AS plugin ON plugin.id = credential.plugin_id
                JOIN company_plugins AS company_plugin
                  ON company_plugin.company_id = credential.company_id
                 AND company_plugin.plugin_id = credential.plugin_id
                WHERE credential.company_id = :company_id
                  AND credential.status = 'active'
                  AND plugin.code = 'rest_api'
                  AND company_plugin.status = 'active'
                  AND (
                      credential.expires_at IS NULL
                      OR credential.expires_at > now()
                  )
                ORDER BY credential.name
                """
            ),
            {"company_id": company_id},
        )
    ).all()
    return [CustomerSyncCredentialOptionResponse(**row._mapping) for row in rows]


async def requeue_sync_dispatch(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    dispatch_id: UUID,
) -> CustomerSyncDispatchResponse:
    updated = (
        await database.execute(
            text(
                """
                UPDATE customer_sync_dispatches
                SET
                    status = 'pending',
                    attempts = 0,
                    available_at = now(),
                    claim_fingerprint = NULL,
                    claim_expires_at = NULL,
                    error_code = NULL,
                    response_status_code = NULL,
                    response_bytes = 0,
                    records_received = 0,
                    result_fingerprint = NULL,
                    completed_at = NULL
                WHERE company_id = :company_id
                  AND id = :dispatch_id
                  AND status IN ('failed', 'dead_letter')
                RETURNING id
                """
            ),
            {"company_id": company_id, "dispatch_id": dispatch_id},
        )
    ).scalar_one_or_none()
    if updated is None:
        raise ValueError("Somente despachos com falha podem ser reenviados.")
    await _governance_event(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        event_type="customer.sync_dispatch.requeued",
        subject_type="sync_dispatch",
        subject_id=dispatch_id,
        payload={"reason": "manual_retry_after_review"},
    )
    rows = await list_sync_dispatches(database, company_id=company_id, limit=200)
    return next(row for row in rows if row.id == dispatch_id)


async def _schedule_company(
    database: AsyncSession,
    *,
    company_id: UUID,
    worker_fingerprint: str,
    limit: int,
) -> tuple[int, int, int]:
    await database.execute(
        text(
            """
            SELECT set_config(
                'app.current_company_id',
                CAST(:company_id AS text),
                true
            )
            """
        ),
        {"company_id": company_id},
    )
    connectors = (
        await database.execute(
            text(
                """
                SELECT
                    connector.id,
                    connector.adapter_key,
                    connector.adapter_version,
                    connector.transport,
                    connector.credential_binding_id,
                    connector.created_by_user_id,
                    connector.next_run_at,
                    connector.schedule_minutes,
                    connection.success AS connection_test_success,
                    COALESCE(connection.duration_ms, 0) AS connection_duration_ms
                FROM customer_sync_connectors AS connector
                LEFT JOIN LATERAL (
                    SELECT test.success, test.duration_ms
                    FROM plugin_connection_tests AS test
                    WHERE test.company_id = connector.company_id
                      AND test.credential_id = connector.credential_binding_id
                    ORDER BY test.created_at DESC
                    LIMIT 1
                ) AS connection ON true
                WHERE connector.company_id = :company_id
                  AND connector.status = 'active'
                  AND connector.next_run_at IS NOT NULL
                  AND connector.next_run_at <= now()
                  AND (connector.lease_until IS NULL OR connector.lease_until <= now())
                ORDER BY connector.next_run_at
                FOR UPDATE OF connector SKIP LOCKED
                LIMIT :limit
                """
            ),
            {"company_id": company_id, "limit": limit},
        )
    ).all()
    evaluated = 0
    dispatched = 0
    blocked = 0
    for connector in connectors:
        evaluated += 1
        definition = get_sync_adapter_definition(connector.adapter_key)
        readiness = evaluate_adapter_readiness(
            adapter_key=connector.adapter_key,
            transport=connector.transport,
            credential_configured=connector.credential_binding_id is not None,
            connection_test_success=connector.connection_test_success,
        )
        await _record_health(
            database,
            company_id=company_id,
            connector=connector,
            readiness=readiness,
        )
        if (
            definition is None
            or not definition.supports_scheduled_dispatch
            or not readiness.can_dispatch
        ):
            blocked += 1
            await database.execute(
                text(
                    """
                    UPDATE customer_sync_connectors
                    SET
                        next_run_at = now() + (
                            LEAST(schedule_minutes, 15) * interval '1 minute'
                        ),
                        updated_at = now()
                    WHERE company_id = :company_id AND id = :connector_id
                    """
                ),
                {"company_id": company_id, "connector_id": connector.id},
            )
            continue
        inserted = (
            await database.execute(
                text(
                    """
                    INSERT INTO customer_sync_dispatches (
                        id, company_id, connector_id, adapter_key, adapter_version,
                        schedule_slot, status, attempts, available_at,
                        scheduler_fingerprint
                    ) VALUES (
                        gen_random_uuid(), :company_id, :connector_id, :adapter_key,
                        :adapter_version, :schedule_slot, 'pending', 0, now(),
                        :scheduler_fingerprint
                    )
                    ON CONFLICT (company_id, connector_id, schedule_slot) DO NOTHING
                    RETURNING id
                    """
                ),
                {
                    "company_id": company_id,
                    "connector_id": connector.id,
                    "adapter_key": connector.adapter_key,
                    "adapter_version": connector.adapter_version,
                    "schedule_slot": connector.next_run_at,
                    "scheduler_fingerprint": worker_fingerprint,
                },
            )
        ).scalar_one_or_none()
        await database.execute(
            text(
                """
                UPDATE customer_sync_connectors
                SET
                    next_run_at = now() + (:schedule_minutes * interval '1 minute'),
                    updated_at = now()
                WHERE company_id = :company_id AND id = :connector_id
                """
            ),
            {
                "company_id": company_id,
                "connector_id": connector.id,
                "schedule_minutes": connector.schedule_minutes,
            },
        )
        if inserted is not None:
            dispatched += 1
            await _governance_event(
                database,
                company_id=company_id,
                actor_user_id=connector.created_by_user_id,
                event_type="customer.sync_dispatch.queued",
                subject_type="sync_dispatch",
                subject_id=inserted,
                payload={
                    "adapter_key": connector.adapter_key,
                    "schedule_slot": connector.next_run_at.isoformat(),
                },
            )
    return evaluated, dispatched, blocked


async def schedule_due_sync_connectors(
    database: AsyncSession,
    *,
    worker_id: str,
    company_limit: int = 100,
    connector_limit: int = 100,
) -> SchedulerResult:
    company_rows = (
        await database.execute(
            text(
                """
                SELECT company_id
                FROM orkestral_due_sync_companies(:company_limit)
                """
            ),
            {"company_limit": company_limit},
        )
    ).all()
    evaluated = 0
    dispatched = 0
    blocked = 0
    worker_fingerprint = _worker_fingerprint(worker_id)
    for row in company_rows:
        company_evaluated, company_dispatched, company_blocked = await _schedule_company(
            database,
            company_id=row.company_id,
            worker_fingerprint=worker_fingerprint,
            limit=connector_limit,
        )
        evaluated += company_evaluated
        dispatched += company_dispatched
        blocked += company_blocked
    await database.execute(text("SELECT set_config('app.current_company_id', '', true)"))
    return SchedulerResult(
        companies=len(company_rows),
        evaluated=evaluated,
        dispatched=dispatched,
        blocked=blocked,
    )


async def _maintain_schedules() -> dict[str, int]:
    settings = get_settings()
    resources = create_resources(settings, database_role="worker")
    try:
        async with resources.sessions() as database:
            result = await schedule_due_sync_connectors(
                database,
                worker_id=f"{socket.gethostname()}:{id(asyncio.current_task())}",
            )
            await database.commit()
            return {
                "companies": result.companies,
                "evaluated": result.evaluated,
                "dispatched": result.dispatched,
                "blocked": result.blocked,
            }
    finally:
        await resources.close()


def maintain_customer_sync_schedules_sync() -> dict[str, int]:
    return asyncio.run(_maintain_schedules())
