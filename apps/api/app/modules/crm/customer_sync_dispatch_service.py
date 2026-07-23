from __future__ import annotations

import asyncio
import hashlib
import json
import socket
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import apply_tenant_database_context
from app.core.resources import create_resources
from app.modules.crm.customer_sync_rest_adapter import (
    RestPullAdapterError,
    pull_customer_records,
)
from app.modules.crm.customer_sync_schemas import CustomerSyncExecutionCreate
from app.modules.crm.customer_sync_service import (
    execute_customer_sync,
    retry_delay_seconds,
)
from app.modules.plugins.crypto import CredentialVault, CredentialVaultError

DispatchOutcome = Literal["acknowledged", "retried", "dead_letter", "skipped"]


@dataclass(frozen=True, slots=True)
class DispatchExecutorResult:
    companies: int
    claimed: int
    acknowledged: int
    retried: int
    dead_letter: int
    skipped: int


@dataclass(frozen=True, slots=True)
class DispatchFailure:
    code: str
    retryable: bool
    status_code: int | None = None


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _vault(settings: Settings) -> CredentialVault:
    return CredentialVault(",".join((settings.encryption_key, *settings.encryption_previous_keys)))


async def _governance_event(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    event_type: str,
    subject_id: UUID,
    payload: dict[str, Any],
) -> None:
    await database.execute(
        text(
            """
            INSERT INTO customer_data_governance_events (
                company_id, actor_user_id, event_type, subject_type, subject_id, payload
            ) VALUES (
                :company_id, :actor_user_id, :event_type, 'sync_dispatch',
                :subject_id, CAST(:payload AS jsonb)
            )
            """
        ),
        {
            "company_id": company_id,
            "actor_user_id": actor_user_id,
            "event_type": event_type,
            "subject_id": subject_id,
            "payload": json.dumps(payload),
        },
    )


async def _claim_dispatches(
    database: AsyncSession,
    *,
    company_id: UUID,
    worker_fingerprint: str,
    limit: int,
    claim_seconds: int,
) -> list[UUID]:
    await database.execute(
        text(
            """
            UPDATE customer_sync_dispatches AS dispatch
            SET
                status = 'dead_letter',
                error_code = COALESCE(error_code, 'MAX_ATTEMPTS_EXCEEDED'),
                completed_at = now(),
                claim_fingerprint = NULL,
                claim_expires_at = NULL
            FROM customer_sync_connectors AS connector
            WHERE dispatch.company_id = :company_id
              AND connector.company_id = dispatch.company_id
              AND connector.id = dispatch.connector_id
              AND dispatch.status IN ('pending', 'failed')
              AND dispatch.attempts >= connector.max_attempts
            """
        ),
        {"company_id": company_id},
    )
    rows = (
        await database.execute(
            text(
                """
                WITH candidates AS (
                    SELECT dispatch.id
                    FROM customer_sync_dispatches AS dispatch
                    JOIN customer_sync_connectors AS connector
                      ON connector.company_id = dispatch.company_id
                     AND connector.id = dispatch.connector_id
                    WHERE dispatch.company_id = :company_id
                      AND connector.status = 'active'
                      AND connector.adapter_key = 'generic_rest_pull'
                      AND dispatch.attempts < connector.max_attempts
                      AND (
                          (
                              dispatch.status IN ('pending', 'failed')
                              AND dispatch.available_at <= now()
                          )
                          OR (
                              dispatch.status = 'claimed'
                              AND dispatch.claim_expires_at <= now()
                          )
                      )
                    ORDER BY dispatch.available_at, dispatch.created_at
                    FOR UPDATE OF dispatch SKIP LOCKED
                    LIMIT :limit
                )
                UPDATE customer_sync_dispatches AS dispatch
                SET
                    status = 'claimed',
                    attempts = dispatch.attempts + 1,
                    claim_fingerprint = :worker_fingerprint,
                    claimed_at = now(),
                    claim_expires_at = now() + (:claim_seconds * interval '1 second'),
                    completed_at = NULL,
                    error_code = NULL
                FROM candidates
                WHERE dispatch.company_id = :company_id
                  AND dispatch.id = candidates.id
                RETURNING dispatch.id
                """
            ),
            {
                "company_id": company_id,
                "worker_fingerprint": worker_fingerprint,
                "limit": limit,
                "claim_seconds": claim_seconds,
            },
        )
    ).all()
    return [row.id for row in rows]


async def _load_claimed_dispatch(
    database: AsyncSession,
    *,
    company_id: UUID,
    dispatch_id: UUID,
    worker_fingerprint: str,
) -> Any:
    return (
        await database.execute(
            text(
                """
                SELECT
                    dispatch.id,
                    dispatch.connector_id,
                    dispatch.attempts,
                    connector.cursor,
                    connector.max_attempts,
                    connector.base_backoff_seconds,
                    connector.created_by_user_id,
                    credential.encrypted_credentials,
                    credential.status AS credential_status,
                    credential.expires_at AS credential_expires_at
                FROM customer_sync_dispatches AS dispatch
                JOIN customer_sync_connectors AS connector
                  ON connector.company_id = dispatch.company_id
                 AND connector.id = dispatch.connector_id
                LEFT JOIN integration_credentials AS credential
                  ON credential.company_id = connector.company_id
                 AND credential.id = connector.credential_binding_id
                WHERE dispatch.company_id = :company_id
                  AND dispatch.id = :dispatch_id
                  AND dispatch.status = 'claimed'
                  AND dispatch.claim_fingerprint = :worker_fingerprint
                """
            ),
            {
                "company_id": company_id,
                "dispatch_id": dispatch_id,
                "worker_fingerprint": worker_fingerprint,
            },
        )
    ).one_or_none()


async def _record_dispatch_failure(
    database: AsyncSession,
    *,
    company_id: UUID,
    dispatch: Any,
    worker_fingerprint: str,
    failure: DispatchFailure,
) -> DispatchOutcome:
    terminal = not failure.retryable or dispatch.attempts >= dispatch.max_attempts
    delay = retry_delay_seconds(dispatch.base_backoff_seconds, dispatch.attempts)
    available_at = datetime.now(UTC) + timedelta(seconds=delay)
    target_status = "dead_letter" if terminal else "failed"
    await database.execute(
        text(
            """
            UPDATE customer_sync_dispatches
            SET
                status = CAST(:target_status AS varchar),
                available_at = :available_at,
                error_code = :error_code,
                response_status_code = :response_status_code,
                claim_fingerprint = NULL,
                claim_expires_at = NULL,
                completed_at = CASE
                    WHEN CAST(:target_status AS varchar) = 'dead_letter' THEN now()
                    ELSE NULL
                END
            WHERE company_id = :company_id
              AND id = :dispatch_id
              AND status = 'claimed'
              AND claim_fingerprint = :worker_fingerprint
            """
        ),
        {
            "company_id": company_id,
            "dispatch_id": dispatch.id,
            "worker_fingerprint": worker_fingerprint,
            "target_status": target_status,
            "available_at": available_at,
            "error_code": failure.code[:80],
            "response_status_code": failure.status_code,
        },
    )
    await database.execute(
        text(
            """
            UPDATE customer_sync_connectors
            SET
                consecutive_failures = consecutive_failures + 1,
                next_run_at = :available_at,
                updated_at = now()
            WHERE company_id = :company_id AND id = :connector_id
            """
        ),
        {
            "company_id": company_id,
            "connector_id": dispatch.connector_id,
            "available_at": available_at,
        },
    )
    await _governance_event(
        database,
        company_id=company_id,
        actor_user_id=dispatch.created_by_user_id,
        event_type=(
            "customer.sync_dispatch.dead_letter"
            if terminal
            else "customer.sync_dispatch.retry_scheduled"
        ),
        subject_id=dispatch.id,
        payload={
            "error_code": failure.code[:80],
            "attempt": dispatch.attempts,
            "retryable": failure.retryable,
        },
    )
    return "dead_letter" if terminal else "retried"


async def _acknowledge_dispatch(
    database: AsyncSession,
    *,
    company_id: UUID,
    dispatch: Any,
    worker_fingerprint: str,
    run_id: UUID | None,
    status_code: int,
    response_bytes: int,
    records_received: int,
    result_fingerprint: str,
) -> DispatchOutcome:
    await database.execute(
        text(
            """
            UPDATE customer_sync_dispatches
            SET
                status = 'acknowledged',
                run_id = :run_id,
                response_status_code = :status_code,
                response_bytes = :response_bytes,
                records_received = :records_received,
                result_fingerprint = :result_fingerprint,
                claim_fingerprint = NULL,
                claim_expires_at = NULL,
                error_code = NULL,
                completed_at = now()
            WHERE company_id = :company_id
              AND id = :dispatch_id
              AND status = 'claimed'
              AND claim_fingerprint = :worker_fingerprint
            """
        ),
        {
            "company_id": company_id,
            "dispatch_id": dispatch.id,
            "worker_fingerprint": worker_fingerprint,
            "run_id": run_id,
            "status_code": status_code,
            "response_bytes": response_bytes,
            "records_received": records_received,
            "result_fingerprint": result_fingerprint,
        },
    )
    await _governance_event(
        database,
        company_id=company_id,
        actor_user_id=dispatch.created_by_user_id,
        event_type="customer.sync_dispatch.acknowledged",
        subject_id=dispatch.id,
        payload={
            "records_received": records_received,
            "run_id": str(run_id) if run_id else None,
        },
    )
    return "acknowledged"


async def _process_claimed_dispatch(
    database: AsyncSession,
    *,
    settings: Settings,
    company_id: UUID,
    dispatch_id: UUID,
    worker_fingerprint: str,
) -> DispatchOutcome:
    dispatch = await _load_claimed_dispatch(
        database,
        company_id=company_id,
        dispatch_id=dispatch_id,
        worker_fingerprint=worker_fingerprint,
    )
    if dispatch is None:
        return "skipped"
    now = datetime.now(UTC)
    if (
        dispatch.encrypted_credentials is None
        or dispatch.credential_status != "active"
        or (
            dispatch.credential_expires_at is not None
            and dispatch.credential_expires_at <= now
        )
    ):
        return await _record_dispatch_failure(
            database,
            company_id=company_id,
            dispatch=dispatch,
            worker_fingerprint=worker_fingerprint,
            failure=DispatchFailure("CREDENTIAL_UNAVAILABLE", False),
        )
    try:
        credentials = _vault(settings).decrypt(dispatch.encrypted_credentials)
        batch = await pull_customer_records(
            credentials,
            cursor=dispatch.cursor,
            timeout_seconds=settings.customer_sync_http_timeout_seconds,
            max_response_bytes=settings.customer_sync_http_max_response_bytes,
        )
    except CredentialVaultError:
        failure = DispatchFailure("CREDENTIAL_DECRYPTION_FAILED", False)
    except RestPullAdapterError as exc:
        failure = DispatchFailure(exc.code, exc.retryable, exc.status_code)
    except Exception:
        failure = DispatchFailure("SYNC_EXECUTION_FAILED", True)
    else:
        if not batch.records:
            return await _acknowledge_dispatch(
                database,
                company_id=company_id,
                dispatch=dispatch,
                worker_fingerprint=worker_fingerprint,
                run_id=None,
                status_code=batch.status_code,
                response_bytes=batch.response_bytes,
                records_received=0,
                result_fingerprint=batch.response_fingerprint,
            )
        try:
            run = await execute_customer_sync(
                database,
                company_id=company_id,
                actor_user_id=dispatch.created_by_user_id,
                connector_id=dispatch.connector_id,
                payload=CustomerSyncExecutionCreate(
                    idempotency_key=(
                        f"dispatch:{dispatch.id}:attempt:{dispatch.attempts}"
                    ),
                    trigger="scheduled",
                    cursor_after=batch.cursor_after,
                    records=list(batch.records),
                ),
            )
        except (LookupError, ValueError):
            failure = DispatchFailure("SYNC_INGESTION_UNAVAILABLE", True)
        except Exception:
            failure = DispatchFailure("SYNC_INGESTION_FAILED", True)
        else:
            if run.status == "failed":
                failure = DispatchFailure(run.error_code or "SYNC_INPUT_REJECTED", False)
            else:
                result_fingerprint = hashlib.sha256(
                    (
                        f"{batch.response_fingerprint}:{run.id}:"
                        f"{run.accepted_records}:{run.rejected_records}"
                    ).encode()
                ).hexdigest()
                return await _acknowledge_dispatch(
                    database,
                    company_id=company_id,
                    dispatch=dispatch,
                    worker_fingerprint=worker_fingerprint,
                    run_id=run.id,
                    status_code=batch.status_code,
                    response_bytes=batch.response_bytes,
                    records_received=len(batch.records),
                    result_fingerprint=result_fingerprint,
                )
    return await _record_dispatch_failure(
        database,
        company_id=company_id,
        dispatch=dispatch,
        worker_fingerprint=worker_fingerprint,
        failure=failure,
    )


async def execute_customer_sync_dispatches(
    *,
    worker_id: str,
    company_limit: int = 100,
) -> DispatchExecutorResult:
    settings = get_settings()
    resources = create_resources(settings, database_role="worker")
    worker_fingerprint = _fingerprint(worker_id)
    claimed = acknowledged = retried = dead_letter = skipped = 0
    try:
        async with resources.sessions() as discovery:
            companies = (
                await discovery.execute(
                    text(
                        """
                        SELECT company_id
                        FROM orkestral_due_sync_dispatch_companies(:company_limit)
                        """
                    ),
                    {"company_limit": company_limit},
                )
            ).all()
        for company in companies:
            async with resources.sessions() as database:
                await apply_tenant_database_context(
                    database,
                    company_id=company.company_id,
                    access_mode="standard",
                )
                dispatch_ids = await _claim_dispatches(
                    database,
                    company_id=company.company_id,
                    worker_fingerprint=worker_fingerprint,
                    limit=settings.customer_sync_dispatch_batch_size,
                    claim_seconds=settings.customer_sync_dispatch_claim_seconds,
                )
                claimed += len(dispatch_ids)
                await database.commit()
                for dispatch_id in dispatch_ids:
                    outcome = await _process_claimed_dispatch(
                        database,
                        settings=settings,
                        company_id=company.company_id,
                        dispatch_id=dispatch_id,
                        worker_fingerprint=worker_fingerprint,
                    )
                    await database.commit()
                    if outcome == "acknowledged":
                        acknowledged += 1
                    elif outcome == "retried":
                        retried += 1
                    elif outcome == "dead_letter":
                        dead_letter += 1
                    else:
                        skipped += 1
        return DispatchExecutorResult(
            companies=len(companies),
            claimed=claimed,
            acknowledged=acknowledged,
            retried=retried,
            dead_letter=dead_letter,
            skipped=skipped,
        )
    finally:
        await resources.close()


async def _execute_dispatches() -> dict[str, int]:
    result = await execute_customer_sync_dispatches(
        worker_id=f"{socket.gethostname()}:{id(asyncio.current_task())}",
    )
    return {
        "companies": result.companies,
        "claimed": result.claimed,
        "acknowledged": result.acknowledged,
        "retried": result.retried,
        "dead_letter": result.dead_letter,
        "skipped": result.skipped,
    }


def execute_customer_sync_dispatches_sync() -> dict[str, int]:
    return asyncio.run(_execute_dispatches())
