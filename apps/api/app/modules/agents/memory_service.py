from __future__ import annotations

import hashlib
import hmac
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import perf_counter
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.resources import create_resources
from app.core.security import utc_now
from app.modules.agents.coordination_models import AgentDelegation
from app.modules.agents.memory_models import (
    AgentMemoryEntry,
    AgentMemoryExerciseSchedule,
    AgentMemoryLegalHold,
    AgentMemoryPolicy,
    AgentMemoryPurposePolicy,
    AgentMemoryReencryptionJob,
    AgentMemoryResponseExercise,
    AgentMemoryRiskReportRecord,
    AgentMemoryScopePolicy,
    AgentTaskMemoryAccessGrant,
    AgentTaskMemoryAccessIncident,
)
from app.modules.agents.models import AgentDataPolicy
from app.modules.agents.security import (
    CLASSIFICATION_RANK,
    protect_provider_text,
    scan_prompt_injection,
)
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.notifications.service import create_notification
from app.modules.plugins.crypto import CredentialVault, CredentialVaultError

DEFAULT_SCOPES = ["conversation", "task", "operational"]
DEFAULT_CLASSIFICATIONS = ["public", "internal"]


@dataclass(frozen=True, slots=True)
class AuthorizedMemoryContext:
    contents: tuple[str, ...]
    retrieved_fingerprints: tuple[str, ...]
    blocked_fingerprints: tuple[str, ...]
    estimated_tokens: int


@dataclass(frozen=True, slots=True)
class SharedTaskMemoryItem:
    memory_id: UUID
    owner_agent_id: UUID
    classification: str
    purpose: str
    content: str
    truncated: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SharedTaskMemoryContext:
    items: tuple[SharedTaskMemoryItem, ...]
    total_characters: int
    blocked_items: int


def memory_content_fingerprint(
    *,
    secret: str,
    company_id: UUID,
    agent_id: UUID,
    scope: str,
    purpose: str,
    subject_user_id: UUID | None,
    content: str,
    task_delegation_id: UUID | None = None,
) -> str:
    payload = (
        f"{company_id}:{agent_id}:{scope}:{purpose}:{subject_user_id or '-'}:"
        f"{task_delegation_id or '-'}:{content}"
    ).encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def memory_consent_fingerprint(
    *, secret: str, company_id: UUID, agent_id: UUID, subject_user_id: UUID, reference: str
) -> str:
    payload = f"{company_id}:{agent_id}:{subject_user_id}:{reference}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def memory_legal_reference_fingerprint(
    *, secret: str, company_id: UUID, agent_id: UUID, delegation_id: UUID, reference: str
) -> str:
    payload = f"{company_id}:{agent_id}:{delegation_id}:{reference}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def memory_access_revocation_fingerprint(
    *, secret: str, company_id: UUID, grant_id: UUID, reason: str
) -> str:
    payload = f"{company_id}:{grant_id}:{reason}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def memory_incident_value_fingerprint(
    *, secret: str, company_id: UUID, agent_id: UUID, value_type: str, value: str
) -> str:
    payload = f"{company_id}:{agent_id}:{value_type}:{value}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def memory_master_key_id(secret: str) -> str:
    return hashlib.sha256(f"orkestral-memory-master:{secret}".encode()).hexdigest()[:32]


def memory_signing_secrets(settings: Settings, master_key_id: str) -> tuple[str, ...]:
    candidates = tuple(dict.fromkeys((settings.encryption_key, *settings.encryption_previous_keys)))
    if master_key_id == "legacy":
        return candidates
    return tuple(secret for secret in candidates if memory_master_key_id(secret) == master_key_id)


def memory_credential_vault(settings: Settings) -> CredentialVault:
    return CredentialVault(",".join((settings.encryption_key, *settings.encryption_previous_keys)))


async def memory_response_exercise_checks(
    database: AsyncSession, *, company_id: UUID, agent_id: UUID
) -> dict[str, bool]:
    quarantine_violations = int(
        await database.scalar(
            select(func.count(AgentTaskMemoryAccessGrant.id))
            .select_from(AgentTaskMemoryAccessGrant)
            .join(
                AgentTaskMemoryAccessIncident,
                and_(
                    AgentTaskMemoryAccessIncident.company_id
                    == AgentTaskMemoryAccessGrant.company_id,
                    AgentTaskMemoryAccessIncident.owner_agent_id
                    == AgentTaskMemoryAccessGrant.owner_agent_id,
                    AgentTaskMemoryAccessGrant.created_at
                    >= AgentTaskMemoryAccessIncident.created_at,
                    AgentTaskMemoryAccessGrant.created_at
                    < AgentTaskMemoryAccessIncident.quarantine_until,
                ),
            )
            .where(
                AgentTaskMemoryAccessGrant.company_id == company_id,
                AgentTaskMemoryAccessGrant.owner_agent_id == agent_id,
                AgentTaskMemoryAccessGrant.status == "active",
            )
        )
        or 0
    )
    quorum_violations = int(
        await database.scalar(
            select(func.count(AgentTaskMemoryAccessIncident.id)).where(
                AgentTaskMemoryAccessIncident.company_id == company_id,
                AgentTaskMemoryAccessIncident.owner_agent_id == agent_id,
                AgentTaskMemoryAccessIncident.severity == "critical",
                or_(
                    and_(
                        AgentTaskMemoryAccessIncident.review_status != "pending",
                        AgentTaskMemoryAccessIncident.review_count
                        < AgentTaskMemoryAccessIncident.required_review_quorum,
                    ),
                    and_(
                        AgentTaskMemoryAccessIncident.review_status == "pending",
                        AgentTaskMemoryAccessIncident.review_count
                        >= AgentTaskMemoryAccessIncident.required_review_quorum,
                    ),
                ),
            )
        )
        or 0
    )
    tenant_mismatches = sum(
        int(value or 0)
        for value in (
            await database.scalar(
                select(func.count(AgentTaskMemoryAccessGrant.id)).where(
                    AgentTaskMemoryAccessGrant.owner_agent_id == agent_id,
                    AgentTaskMemoryAccessGrant.company_id != company_id,
                )
            ),
            await database.scalar(
                select(func.count(AgentTaskMemoryAccessIncident.id)).where(
                    AgentTaskMemoryAccessIncident.owner_agent_id == agent_id,
                    AgentTaskMemoryAccessIncident.company_id != company_id,
                )
            ),
            await database.scalar(
                select(func.count(AgentMemoryRiskReportRecord.id)).where(
                    AgentMemoryRiskReportRecord.agent_id == agent_id,
                    AgentMemoryRiskReportRecord.company_id != company_id,
                )
            ),
        )
    )
    report_records = list(
        await database.scalars(
            select(AgentMemoryRiskReportRecord)
            .where(
                AgentMemoryRiskReportRecord.company_id == company_id,
                AgentMemoryRiskReportRecord.agent_id == agent_id,
            )
            .order_by(AgentMemoryRiskReportRecord.sequence)
        )
    )
    report_chain_intact = all(
        record.sequence == index + 1
        and record.previous_signature == (report_records[index - 1].signature if index else None)
        for index, record in enumerate(report_records)
    )
    return {
        "quarantine_enforced": quarantine_violations == 0,
        "critical_quorum_enforced": quorum_violations == 0,
        "tenant_scope_intact": tenant_mismatches == 0,
        "report_chain_intact": report_chain_intact,
    }


async def record_agent_memory_response_exercise(
    database: AsyncSession,
    *,
    company_id: UUID,
    agent_id: UUID,
    requested_by_user_id: UUID,
    source: str,
) -> AgentMemoryResponseExercise:
    started = perf_counter()
    checks = await memory_response_exercise_checks(
        database, company_id=company_id, agent_id=agent_id
    )
    exercise = AgentMemoryResponseExercise(
        company_id=company_id,
        agent_id=agent_id,
        scenario="full",
        status="passed" if all(checks.values()) else "failed",
        checks=checks,
        source=source,
        duration_ms=max(0, round((perf_counter() - started) * 1000)),
        requested_by_user_id=requested_by_user_id,
    )
    database.add(exercise)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=requested_by_user_id,
        action="agent.memory_response_exercise.completed",
        target_type="agent_memory_response_exercise",
        target_id=exercise.id,
        details={"status": exercise.status, "checks": checks, "source": source},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.memory_response_exercise.completed",
            company_id=company_id,
            actor_user_id=requested_by_user_id,
            classification="internal",
            payload={
                "exercise_id": str(exercise.id),
                "status": exercise.status,
                "source": source,
            },
        ),
    )
    return exercise


def memory_is_expired(memory: AgentMemoryEntry, *, now: datetime | None = None) -> bool:
    return memory.expires_at <= (now or utc_now())


def estimate_memory_tokens(content: str) -> int:
    return max(1, (len(content) + 3) // 4)


def memory_policy_values(
    policy: AgentMemoryPolicy | None,
    scope_policies: Sequence[AgentMemoryScopePolicy] = (),
    purpose_policies: Sequence[AgentMemoryPurposePolicy] = (),
) -> dict[str, object]:
    if policy is None:
        return {
            "default_retention_days": 30,
            "max_retention_days": 365,
            "allowed_scopes": DEFAULT_SCOPES,
            "allowed_classifications": DEFAULT_CLASSIFICATIONS,
            "require_consent_for_user_scope": True,
            "retrieval_enabled": False,
            "max_retrieval_entries": 5,
            "max_context_tokens": 1000,
            "max_shared_context_entries": 5,
            "max_shared_context_characters": 2000,
            "blocked_context_alert_threshold": 3,
            "scope_policies": [
                {
                    "scope": scope,
                    "retention_days": 30,
                    "retrieval_enabled": True,
                }
                for scope in DEFAULT_SCOPES
            ],
            "purpose_policies": [
                {
                    "purpose": "operations",
                    "retention_days": 30,
                    "enabled": True,
                }
            ],
        }
    configured = {item.scope: item for item in scope_policies}
    effective_scopes = [
        {
            "scope": scope,
            "retention_days": configured[scope].retention_days
            if scope in configured
            else policy.default_retention_days,
            "retrieval_enabled": configured[scope].retrieval_enabled
            if scope in configured
            else True,
        }
        for scope in policy.allowed_scopes
    ]
    effective_purposes = [
        {
            "purpose": item.purpose,
            "retention_days": item.retention_days,
            "enabled": item.enabled,
        }
        for item in purpose_policies
    ] or [
        {
            "purpose": "operations",
            "retention_days": policy.default_retention_days,
            "enabled": True,
        }
    ]
    return {
        "default_retention_days": policy.default_retention_days,
        "max_retention_days": policy.max_retention_days,
        "allowed_scopes": policy.allowed_scopes,
        "allowed_classifications": policy.allowed_classifications,
        "require_consent_for_user_scope": policy.require_consent_for_user_scope,
        "retrieval_enabled": policy.retrieval_enabled,
        "max_retrieval_entries": policy.max_retrieval_entries,
        "max_context_tokens": policy.max_context_tokens,
        "max_shared_context_entries": policy.max_shared_context_entries,
        "max_shared_context_characters": policy.max_shared_context_characters,
        "blocked_context_alert_threshold": policy.blocked_context_alert_threshold,
        "scope_policies": effective_scopes,
        "purpose_policies": effective_purposes,
    }


async def retrieve_authorized_memories(
    database: AsyncSession,
    *,
    settings: Settings,
    company_id: UUID,
    agent_id: UUID,
    user_id: UUID,
    provider: str,
    memory_policy: AgentMemoryPolicy | None,
    scope_policies: Sequence[AgentMemoryScopePolicy],
    data_policy: AgentDataPolicy,
) -> AuthorizedMemoryContext:
    if memory_policy is None or not memory_policy.retrieval_enabled:
        return AuthorizedMemoryContext((), (), (), 0)
    maximum_rank = CLASSIFICATION_RANK[data_policy.max_data_classification]
    allowed = [
        classification
        for classification in memory_policy.allowed_classifications
        if CLASSIFICATION_RANK[classification] <= maximum_rank
    ]
    if not allowed:
        return AuthorizedMemoryContext((), (), (), 0)
    values = memory_policy_values(memory_policy, scope_policies)
    effective_scope_policies = cast(list[dict[str, object]], values["scope_policies"])
    retrieval_scopes = [
        str(item["scope"]) for item in effective_scope_policies if bool(item["retrieval_enabled"])
    ]
    if not retrieval_scopes:
        return AuthorizedMemoryContext((), (), (), 0)
    active_task_ids = select(AgentDelegation.id).where(
        AgentDelegation.company_id == company_id,
        AgentDelegation.status.in_(("queued", "in_progress", "awaiting_approval")),
    )
    rows = list(
        await database.scalars(
            select(AgentMemoryEntry)
            .where(
                AgentMemoryEntry.company_id == company_id,
                AgentMemoryEntry.agent_id == agent_id,
                AgentMemoryEntry.expires_at > utc_now(),
                AgentMemoryEntry.classification.in_(allowed),
                AgentMemoryEntry.scope.in_(retrieval_scopes),
                or_(
                    AgentMemoryEntry.scope != "user",
                    AgentMemoryEntry.subject_user_id == user_id,
                ),
                or_(
                    AgentMemoryEntry.scope != "task",
                    AgentMemoryEntry.task_delegation_id.in_(active_task_ids),
                ),
            )
            .order_by(AgentMemoryEntry.created_at.desc())
            .limit(memory_policy.max_retrieval_entries)
        )
    )
    vault = memory_credential_vault(settings)
    contents: list[str] = []
    retrieved: list[str] = []
    blocked: list[str] = []
    estimated_tokens = 0
    for row in rows:
        try:
            content = vault.decrypt(row.encrypted_content).get("content")
        except CredentialVaultError:
            blocked.append(row.content_fingerprint)
            continue
        if not isinstance(content, str):
            blocked.append(row.content_fingerprint)
            continue
        assessment = scan_prompt_injection(content)
        if assessment.detected:
            blocked.append(row.content_fingerprint)
            continue
        protected = protect_provider_text(data_policy, provider=provider, text=content)[0]
        content_tokens = estimate_memory_tokens(protected)
        if estimated_tokens + content_tokens > memory_policy.max_context_tokens:
            continue
        contents.append(protected)
        retrieved.append(row.content_fingerprint)
        estimated_tokens += content_tokens
    return AuthorizedMemoryContext(
        tuple(contents), tuple(retrieved), tuple(blocked), estimated_tokens
    )


async def retrieve_shared_task_memories(
    database: AsyncSession,
    *,
    settings: Settings,
    company_id: UUID,
    grant: AgentTaskMemoryAccessGrant,
    max_entries: int | None = None,
    max_content_characters: int | None = None,
) -> SharedTaskMemoryContext:
    effective_max_entries = min(grant.max_entries, max_entries or grant.max_entries)
    effective_max_characters = min(
        grant.max_content_characters,
        max_content_characters or grant.max_content_characters,
    )
    rows = list(
        await database.scalars(
            select(AgentMemoryEntry)
            .where(
                AgentMemoryEntry.company_id == company_id,
                AgentMemoryEntry.agent_id == grant.owner_agent_id,
                AgentMemoryEntry.scope == "task",
                AgentMemoryEntry.task_delegation_id == grant.task_delegation_id,
                AgentMemoryEntry.classification.in_(grant.allowed_classifications),
                AgentMemoryEntry.expires_at > utc_now(),
            )
            .order_by(AgentMemoryEntry.created_at.desc())
            .limit(effective_max_entries)
        )
    )
    vault = memory_credential_vault(settings)
    items: list[SharedTaskMemoryItem] = []
    remaining_characters = effective_max_characters
    blocked_items = 0
    for row in rows:
        try:
            content = vault.decrypt(row.encrypted_content).get("content")
        except CredentialVaultError:
            blocked_items += 1
            continue
        if not isinstance(content, str) or scan_prompt_injection(content).detected:
            blocked_items += 1
            continue
        if remaining_characters <= 0:
            break
        minimized = content[:remaining_characters]
        if not minimized:
            continue
        items.append(
            SharedTaskMemoryItem(
                memory_id=row.id,
                owner_agent_id=row.agent_id,
                classification=row.classification,
                purpose=row.purpose,
                content=minimized,
                truncated=len(minimized) < len(content),
                created_at=row.created_at,
            )
        )
        remaining_characters -= len(minimized)
    return SharedTaskMemoryContext(
        items=tuple(items),
        total_characters=effective_max_characters - remaining_characters,
        blocked_items=blocked_items,
    )


async def has_active_memory_legal_hold(
    database: AsyncSession,
    *,
    company_id: UUID,
    agent_id: UUID,
    delegation_id: UUID,
) -> bool:
    hold_id = await database.scalar(
        select(AgentMemoryLegalHold.id).where(
            AgentMemoryLegalHold.company_id == company_id,
            AgentMemoryLegalHold.agent_id == agent_id,
            AgentMemoryLegalHold.task_delegation_id == delegation_id,
            AgentMemoryLegalHold.status == "approved",
            AgentMemoryLegalHold.expires_at > utc_now(),
        )
    )
    return hold_id is not None


async def purge_terminal_task_memories(
    database: AsyncSession, *, company_id: UUID, delegation_id: UUID
) -> int:
    rows = list(
        await database.scalars(
            select(AgentMemoryEntry)
            .where(
                AgentMemoryEntry.company_id == company_id,
                AgentMemoryEntry.scope == "task",
                AgentMemoryEntry.task_delegation_id == delegation_id,
            )
            .with_for_update()
        )
    )
    deleted = 0
    for row in rows:
        if await has_active_memory_legal_hold(
            database,
            company_id=company_id,
            agent_id=row.agent_id,
            delegation_id=delegation_id,
        ):
            continue
        await database.delete(row)
        deleted += 1
    return deleted


async def purge_expired_agent_memories(database: AsyncSession, *, limit: int = 1_000) -> int:
    terminal_task_ids = select(AgentDelegation.id).where(
        AgentDelegation.status.in_(("completed", "failed", "cancelled"))
    )
    rows = list(
        await database.scalars(
            select(AgentMemoryEntry)
            .where(
                or_(
                    AgentMemoryEntry.expires_at <= utc_now(),
                    AgentMemoryEntry.task_delegation_id.in_(terminal_task_ids),
                )
            )
            .order_by(AgentMemoryEntry.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    deleted = 0
    for row in rows:
        if row.task_delegation_id is not None and await has_active_memory_legal_hold(
            database,
            company_id=row.company_id,
            agent_id=row.agent_id,
            delegation_id=row.task_delegation_id,
        ):
            continue
        await database.delete(row)
        deleted += 1
    await database.commit()
    return deleted


async def _purge_expired_agent_memories_once(settings: Settings) -> int:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            return await purge_expired_agent_memories(database)
    finally:
        await resources.close()


def purge_expired_agent_memories_sync() -> int:
    import asyncio

    return asyncio.run(_purge_expired_agent_memories_once(get_settings()))


async def run_due_agent_memory_response_exercises(
    database: AsyncSession, *, limit: int = 5000
) -> dict[str, int]:
    now = utc_now()
    schedules = list(
        await database.scalars(
            select(AgentMemoryExerciseSchedule)
            .where(
                AgentMemoryExerciseSchedule.enabled.is_(True),
            )
            .order_by(AgentMemoryExerciseSchedule.updated_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    due_schedules: list[AgentMemoryExerciseSchedule] = []
    slo_breaches = 0
    for schedule in schedules:
        previous_heartbeat = schedule.last_worker_heartbeat_at
        heartbeat_overdue = bool(
            previous_heartbeat
            and now - previous_heartbeat > timedelta(minutes=schedule.heartbeat_slo_minutes)
        )
        if heartbeat_overdue:
            schedule.slo_breach_count += 1
            schedule.last_slo_alert_at = now
            slo_breaches += 1
            await create_notification(
                database,
                company_id=schedule.company_id,
                recipient_user_id=schedule.updated_by_user_id,
                event_type="agent.memory_scheduler.slo_breached",
                title="Agenda de segurança retomada após atraso",
                message="O worker voltou a responder depois de ultrapassar o SLO configurado.",
                severity="error",
                resource_type="agent_memory_exercise_schedule",
                resource_id=schedule.id,
                data={
                    "agent_id": str(schedule.agent_id),
                    "heartbeat_slo_minutes": schedule.heartbeat_slo_minutes,
                },
            )
            enqueue_domain_event(
                database,
                DomainEventCreate(
                    event_type="agent.memory_scheduler.slo_breached",
                    company_id=schedule.company_id,
                    actor_user_id=schedule.updated_by_user_id,
                    classification="internal",
                    payload={
                        "agent_id": str(schedule.agent_id),
                        "schedule_id": str(schedule.id),
                    },
                ),
            )
        schedule.last_worker_heartbeat_at = now
        if schedule.next_run_at is not None and schedule.next_run_at <= now:
            due_schedules.append(schedule)
    passed = failed = 0
    for schedule in due_schedules:
        exercise = await record_agent_memory_response_exercise(
            database,
            company_id=schedule.company_id,
            agent_id=schedule.agent_id,
            requested_by_user_id=schedule.updated_by_user_id,
            source="worker_schedule",
        )
        schedule.last_run_at = now
        schedule.next_run_at = now + timedelta(hours=schedule.cadence_hours)
        if exercise.status == "passed":
            passed += 1
        else:
            failed += 1
            await create_notification(
                database,
                company_id=schedule.company_id,
                recipient_user_id=schedule.updated_by_user_id,
                event_type="agent.memory_response_exercise.failed",
                title="Exercício de segurança exige revisão",
                message="Um controle da memória do agente não passou no exercício agendado.",
                severity="error",
                resource_type="agent_memory_response_exercise",
                resource_id=exercise.id,
                data={"agent_id": str(schedule.agent_id)},
            )
    await database.commit()
    return {
        "processed": len(due_schedules),
        "passed": passed,
        "failed": failed,
        "heartbeat_checked": len(schedules),
        "slo_breaches": slo_breaches,
    }


async def maintain_due_agent_memory_response_exercises(*, settings: Settings) -> dict[str, int]:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            return await run_due_agent_memory_response_exercises(database)
    finally:
        await resources.close()


def maintain_due_agent_memory_response_exercises_sync() -> dict[str, int]:
    import asyncio

    return asyncio.run(maintain_due_agent_memory_response_exercises(settings=get_settings()))


async def process_agent_memory_reencryption_jobs(
    database: AsyncSession, *, settings: Settings, limit: int = 10
) -> dict[str, int]:
    jobs = list(
        await database.scalars(
            select(AgentMemoryReencryptionJob)
            .where(AgentMemoryReencryptionJob.status.in_(("pending", "running")))
            .order_by(AgentMemoryReencryptionJob.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    completed = failed = rotated = 0
    vault = memory_credential_vault(settings)
    active_key_id = memory_master_key_id(settings.encryption_key)
    for job in jobs:
        now = utc_now()
        if job.target_master_key_id != active_key_id:
            job.status = "failed"
            job.error_code = "target_key_changed"
            job.completed_at = now
            job.recovery_status = "not_assessed"
            job.last_recovery_assessment_at = None
            job.recovery_assessed_by_user_id = None
            failed += 1
            continue
        if job.status == "pending":
            job.status = "running"
            job.started_at = now
        checkpoint_conditions = []
        if job.checkpoint_created_at is not None and job.checkpoint_memory_id is not None:
            checkpoint_conditions.append(
                or_(
                    AgentMemoryEntry.created_at > job.checkpoint_created_at,
                    and_(
                        AgentMemoryEntry.created_at == job.checkpoint_created_at,
                        AgentMemoryEntry.id > job.checkpoint_memory_id,
                    ),
                )
            )
        snapshot_conditions = []
        if job.snapshot_created_at is not None and job.snapshot_memory_id is not None:
            snapshot_conditions.append(
                or_(
                    AgentMemoryEntry.created_at < job.snapshot_created_at,
                    and_(
                        AgentMemoryEntry.created_at == job.snapshot_created_at,
                        AgentMemoryEntry.id <= job.snapshot_memory_id,
                    ),
                )
            )
        rows = list(
            await database.scalars(
                select(AgentMemoryEntry)
                .where(
                    AgentMemoryEntry.company_id == job.company_id,
                    AgentMemoryEntry.agent_id == job.agent_id,
                    *checkpoint_conditions,
                    *snapshot_conditions,
                )
                .order_by(AgentMemoryEntry.created_at, AgentMemoryEntry.id)
                .limit(job.batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        job_failed = False
        for memory in rows:
            job.scanned_count += 1
            try:
                memory.encrypted_content = vault.rotate(memory.encrypted_content)
            except CredentialVaultError:
                job.failed_count += 1
                job.status = "failed"
                job.error_code = "memory_decryption_failed"
                job.completed_at = utc_now()
                job.recovery_status = "not_assessed"
                job.last_recovery_assessment_at = None
                job.recovery_assessed_by_user_id = None
                failed += 1
                job_failed = True
                break
            job.rotated_count += 1
            rotated += 1
            job.checkpoint_created_at = memory.created_at
            job.checkpoint_memory_id = memory.id
        if job_failed:
            continue
        if not rows or len(rows) < job.batch_size or job.scanned_count >= job.total_count:
            job.status = "completed"
            job.completed_at = utc_now()
            completed += 1
            record_authorization_audit(
                database,
                company_id=job.company_id,
                actor_user_id=job.requested_by_user_id,
                action="agent.memory_reencryption.completed",
                target_type="agent_memory_reencryption_job",
                target_id=job.id,
                details={
                    "agent_id": str(job.agent_id),
                    "rotated_count": job.rotated_count,
                    "failed_count": job.failed_count,
                },
            )
            enqueue_domain_event(
                database,
                DomainEventCreate(
                    event_type="agent.memory_reencryption.completed",
                    company_id=job.company_id,
                    actor_user_id=job.requested_by_user_id,
                    classification="internal",
                    payload={
                        "job_id": str(job.id),
                        "agent_id": str(job.agent_id),
                        "rotated_count": job.rotated_count,
                    },
                ),
            )
            await create_notification(
                database,
                company_id=job.company_id,
                recipient_user_id=job.requested_by_user_id,
                event_type="agent.memory_reencryption.completed",
                title="Recriptografia de memória concluída",
                message="As memórias do agente foram protegidas pela chave ativa.",
                severity="info",
                resource_type="agent_memory_reencryption_job",
                resource_id=job.id,
                data={"agent_id": str(job.agent_id), "rotated_count": job.rotated_count},
            )
    await database.commit()
    return {
        "processed": len(jobs),
        "completed": completed,
        "failed": failed,
        "rotated": rotated,
    }


async def maintain_agent_memory_reencryption_jobs(*, settings: Settings) -> dict[str, int]:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            return await process_agent_memory_reencryption_jobs(database, settings=settings)
    finally:
        await resources.close()


def maintain_agent_memory_reencryption_jobs_sync() -> dict[str, int]:
    import asyncio

    return asyncio.run(maintain_agent_memory_reencryption_jobs(settings=get_settings()))
