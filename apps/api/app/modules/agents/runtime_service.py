from __future__ import annotations

import asyncio
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.resources import create_resources
from app.core.security import utc_now
from app.modules.agents.models import AgentTool
from app.modules.agents.runtime_models import (
    AgentCredentialBinding,
    AgentEventTrigger,
    AgentExecutionSchedule,
    AgentRuntimeDispatch,
)
from app.modules.events.models import OutboxEvent
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.plugins.models import IntegrationCredential


@dataclass(frozen=True)
class CredentialReadiness:
    ready: bool
    reason_code: str | None
    binding_ids: tuple[UUID, ...]


def objective_fingerprint(secret: str, *, company_id: UUID, agent_id: UUID, objective: str) -> str:
    scope = f"orkestral-agent-objective-v1:{company_id}:{agent_id}:".encode()
    return hmac.new(secret.encode(), scope + objective.encode(), hashlib.sha256).hexdigest()


def next_schedule_time(now: datetime, cadence_minutes: int) -> datetime:
    return now + timedelta(minutes=cadence_minutes)


async def credential_readiness(
    database: AsyncSession,
    *,
    company_id: UUID,
    agent_id: UUID,
    required_tool_keys: list[str],
) -> CredentialReadiness:
    if not required_tool_keys:
        return CredentialReadiness(True, None, ())
    enabled_tool_rows = (
        await database.execute(
            select(AgentTool.tool_key, AgentTool.is_sensitive).where(
                AgentTool.company_id == company_id,
                AgentTool.agent_id == agent_id,
                AgentTool.tool_key.in_(required_tool_keys),
                AgentTool.enabled.is_(True),
            )
        )
    ).all()
    enabled_tools = {tool_key for tool_key, _ in enabled_tool_rows}
    if enabled_tools != set(required_tool_keys):
        return CredentialReadiness(False, "tool_unavailable", ())
    credential_tool_keys = {
        tool_key for tool_key, is_sensitive in enabled_tool_rows if is_sensitive
    }
    if not credential_tool_keys:
        return CredentialReadiness(True, None, ())
    rows = (
        await database.execute(
            select(AgentCredentialBinding, IntegrationCredential)
            .join(
                IntegrationCredential,
                IntegrationCredential.id == AgentCredentialBinding.credential_id,
            )
            .where(
                AgentCredentialBinding.company_id == company_id,
                AgentCredentialBinding.agent_id == agent_id,
                AgentCredentialBinding.tool_key.in_(credential_tool_keys),
                AgentCredentialBinding.enabled.is_(True),
                IntegrationCredential.company_id == company_id,
            )
        )
    ).all()
    by_tool = {binding.tool_key: (binding, credential) for binding, credential in rows}
    if set(by_tool) != credential_tool_keys:
        return CredentialReadiness(False, "credential_binding_missing", ())
    now = utc_now()
    if any(
        credential.status != "active"
        or (credential.expires_at is not None and credential.expires_at <= now)
        for _, credential in by_tool.values()
    ):
        return CredentialReadiness(False, "credential_unavailable", ())
    return CredentialReadiness(
        True,
        None,
        tuple(binding.id for binding, _ in by_tool.values()),
    )


async def _create_dispatch(
    database: AsyncSession,
    settings: Settings,
    *,
    company_id: UUID,
    agent_id: UUID,
    agent_version_id: UUID,
    objective: str,
    required_tool_keys: list[str],
    tool_arguments: dict[str, dict[str, object]],
    execution_mode: str,
    canary_percentage: int,
    scheduled_for: datetime,
    schedule_id: UUID | None = None,
    trigger_id: UUID | None = None,
    source_event_id: UUID | None = None,
) -> AgentRuntimeDispatch:
    readiness = await credential_readiness(
        database,
        company_id=company_id,
        agent_id=agent_id,
        required_tool_keys=required_tool_keys,
    )
    dispatch = AgentRuntimeDispatch(
        company_id=company_id,
        agent_id=agent_id,
        agent_version_id=agent_version_id,
        schedule_id=schedule_id,
        trigger_id=trigger_id,
        source_event_id=source_event_id,
        source_type="schedule" if schedule_id is not None else "event",
        status="ready" if readiness.ready else "blocked",
        reason_code=readiness.reason_code,
        objective_fingerprint=objective_fingerprint(
            settings.encryption_key,
            company_id=company_id,
            agent_id=agent_id,
            objective=objective,
        ),
        required_tool_keys=required_tool_keys,
        credential_binding_ids=[str(value) for value in readiness.binding_ids],
        tool_arguments=tool_arguments,
        execution_mode=execution_mode,
        canary_percentage=canary_percentage,
        scheduled_for=scheduled_for,
    )
    database.add(dispatch)
    await database.flush()
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=f"agent.dispatch.{dispatch.status}",
            company_id=company_id,
            classification="internal",
            payload={
                "agent_id": str(agent_id),
                "dispatch_id": str(dispatch.id),
                "source_type": dispatch.source_type,
                "reason_code": dispatch.reason_code,
            },
        ),
    )
    return dispatch


async def maintain_agent_runtime(
    *, settings: Settings | None = None, limit: int = 100
) -> dict[str, int]:
    active_settings = settings or get_settings()
    resources = create_resources(active_settings)
    result = {"scheduled": 0, "triggered": 0, "ready": 0, "blocked": 0}
    bounded_limit = max(1, min(limit, 500))
    try:
        async with resources.sessions() as database:
            now = utc_now()
            schedules = list(
                await database.scalars(
                    select(AgentExecutionSchedule)
                    .where(
                        AgentExecutionSchedule.status == "published",
                        AgentExecutionSchedule.next_run_at.is_not(None),
                        AgentExecutionSchedule.next_run_at <= now,
                    )
                    .order_by(AgentExecutionSchedule.next_run_at)
                    .with_for_update(skip_locked=True)
                    .limit(bounded_limit)
                )
            )
            for schedule in schedules:
                scheduled_for = schedule.next_run_at or now
                existing = await database.scalar(
                    select(AgentRuntimeDispatch.id).where(
                        AgentRuntimeDispatch.schedule_id == schedule.id,
                        AgentRuntimeDispatch.scheduled_for == scheduled_for,
                    )
                )
                if existing is None:
                    dispatch = await _create_dispatch(
                        database,
                        active_settings,
                        company_id=schedule.company_id,
                        agent_id=schedule.agent_id,
                        agent_version_id=schedule.agent_version_id,
                        objective=schedule.objective,
                        required_tool_keys=schedule.required_tool_keys,
                        tool_arguments=schedule.tool_arguments,
                        execution_mode=schedule.execution_mode,
                        canary_percentage=schedule.canary_percentage,
                        scheduled_for=scheduled_for,
                        schedule_id=schedule.id,
                    )
                    result[dispatch.status] += 1
                    result["scheduled"] += 1
                schedule.last_run_at = scheduled_for
                schedule.next_run_at = next_schedule_time(now, schedule.cadence_minutes)

            remaining = max(0, bounded_limit - result["scheduled"])
            if remaining:
                triggers = list(
                    await database.scalars(
                        select(AgentEventTrigger).where(
                            AgentEventTrigger.status == "published",
                            AgentEventTrigger.published_at.is_not(None),
                        )
                    )
                )
                for trigger in triggers:
                    if result["triggered"] >= remaining:
                        break
                    version_filters = [OutboxEvent.event_version >= trigger.min_event_version]
                    if trigger.max_event_version is not None:
                        version_filters.append(
                            OutboxEvent.event_version <= trigger.max_event_version
                        )
                    events = list(
                        await database.scalars(
                            select(OutboxEvent)
                            .where(
                                OutboxEvent.company_id == trigger.company_id,
                                OutboxEvent.event_type == trigger.event_type,
                                OutboxEvent.created_at >= trigger.published_at,
                                *version_filters,
                                ~select(AgentRuntimeDispatch.id)
                                .where(
                                    AgentRuntimeDispatch.trigger_id == trigger.id,
                                    AgentRuntimeDispatch.source_event_id == OutboxEvent.id,
                                )
                                .correlate(OutboxEvent)
                                .exists(),
                            )
                            .order_by(OutboxEvent.created_at)
                            .limit(remaining - result["triggered"])
                        )
                    )
                    for event in events:
                        dispatch = await _create_dispatch(
                            database,
                            active_settings,
                            company_id=trigger.company_id,
                            agent_id=trigger.agent_id,
                            agent_version_id=trigger.agent_version_id,
                            objective=trigger.objective,
                            required_tool_keys=trigger.required_tool_keys,
                            tool_arguments=trigger.tool_arguments,
                            execution_mode=trigger.execution_mode,
                            canary_percentage=trigger.canary_percentage,
                            scheduled_for=event.created_at,
                            trigger_id=trigger.id,
                            source_event_id=event.id,
                        )
                        result[dispatch.status] += 1
                        result["triggered"] += 1
            await database.commit()
            return result
    finally:
        await resources.close()


def maintain_agent_runtime_sync(limit: int = 100) -> dict[str, int]:
    return asyncio.run(maintain_agent_runtime(limit=limit))
