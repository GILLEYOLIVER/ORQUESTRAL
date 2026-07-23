from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import perf_counter
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.resources import create_resources
from app.core.security import utc_now
from app.modules.agents.approval_policy import (
    ApprovalPolicyDecision,
    evaluate_agent_approval_policy,
)
from app.modules.agents.governance import (
    AgentBudgetExceededError,
    ToolAutonomyDecision,
    evaluate_run_limits,
    evaluate_tool_autonomy,
    reserve_agent_budget,
    settle_agent_budget,
)
from app.modules.agents.models import (
    Agent,
    AgentRun,
    AgentRunStep,
    AgentTool,
    AgentToolRun,
    AgentVersion,
)
from app.modules.agents.runtime_models import (
    AgentEventTrigger,
    AgentExecutionSchedule,
    AgentRuntimeDispatch,
)
from app.modules.agents.tools import (
    ToolAccessError,
    ToolArgumentsError,
    ToolExecutionError,
    assert_tool_access,
    execute_builtin_tool,
    validate_tool_arguments,
)
from app.modules.agents.trace import trace_payload_fingerprint
from app.modules.authorization.models import Permission, RolePermission
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.notifications.service import create_approval_request
from app.modules.users.models import CompanyUser
from app.modules.workflows.definition import as_summary_object


class DispatchExecutionBlocked(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class DispatchSource:
    objective: str
    actor_user_id: UUID


@dataclass(frozen=True, slots=True)
class PreparedTool:
    tool: AgentTool
    arguments: dict[str, Any]
    autonomy: ToolAutonomyDecision
    policy: ApprovalPolicyDecision

    @property
    def requires_approval(self) -> bool:
        return self.autonomy.requires_approval or self.policy.requires_approval


def select_dispatch_execution_mode(
    *, requested_mode: str, canary_percentage: int, fingerprint: str
) -> str:
    if requested_mode != "live" or canary_percentage <= 0:
        return "shadow"
    if canary_percentage >= 100:
        return "live"
    bucket = int(hashlib.sha256(fingerprint.encode()).hexdigest()[:8], 16) % 100
    return "live" if bucket < canary_percentage else "shadow"


def dispatch_status_from_tool_states(
    *, execution_mode: str, states: list[str], denied: bool = False
) -> str:
    if denied or any(state in {"failed", "rejected"} for state in states):
        return "failed"
    if any(state in {"requested", "awaiting_confirmation", "executing"} for state in states):
        return "awaiting_approval"
    if execution_mode != "live":
        return "simulated"
    return "completed" if states and all(state == "completed" for state in states) else "failed"


async def _dispatch_source(
    database: AsyncSession, dispatch: AgentRuntimeDispatch
) -> DispatchSource:
    source: AgentExecutionSchedule | AgentEventTrigger | None
    if dispatch.schedule_id is not None:
        source = await database.scalar(
            select(AgentExecutionSchedule).where(
                AgentExecutionSchedule.id == dispatch.schedule_id,
                AgentExecutionSchedule.company_id == dispatch.company_id,
                AgentExecutionSchedule.agent_id == dispatch.agent_id,
            )
        )
    else:
        source = await database.scalar(
            select(AgentEventTrigger).where(
                AgentEventTrigger.id == dispatch.trigger_id,
                AgentEventTrigger.company_id == dispatch.company_id,
                AgentEventTrigger.agent_id == dispatch.agent_id,
            )
        )
    if source is None:
        raise DispatchExecutionBlocked("source_not_found", "A origem do despacho não existe.")
    return DispatchSource(objective=source.objective, actor_user_id=source.created_by_user_id)


async def _actor_permissions(
    database: AsyncSession, *, company_id: UUID, actor_user_id: UUID
) -> frozenset[str]:
    membership = await database.scalar(
        select(CompanyUser).where(
            CompanyUser.company_id == company_id,
            CompanyUser.user_id == actor_user_id,
            CompanyUser.status == "active",
        )
    )
    if membership is None:
        raise DispatchExecutionBlocked(
            "actor_membership_inactive", "O responsável pelo despacho não está ativo na empresa."
        )
    if membership.is_owner:
        codes = await database.scalars(select(Permission.code))
    elif membership.role_id is not None:
        codes = await database.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == membership.role_id)
        )
    else:
        return frozenset()
    return frozenset(codes.all())


async def _claim_ready_dispatches(
    database: AsyncSession, settings: Settings, *, limit: int
) -> tuple[list[UUID], int]:
    now = utc_now()
    dispatches = list(
        await database.scalars(
            select(AgentRuntimeDispatch)
            .where(AgentRuntimeDispatch.status == "ready")
            .order_by(AgentRuntimeDispatch.created_at)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
    )
    claimed: list[UUID] = []
    failed = 0
    for dispatch in dispatches:
        run: AgentRun | None = None
        try:
            source = await _dispatch_source(database, dispatch)
            agent = await database.scalar(
                select(Agent).where(
                    Agent.id == dispatch.agent_id,
                    Agent.company_id == dispatch.company_id,
                    Agent.status == "active",
                )
            )
            version = await database.scalar(
                select(AgentVersion).where(
                    AgentVersion.id == dispatch.agent_version_id,
                    AgentVersion.agent_id == dispatch.agent_id,
                    AgentVersion.company_id == dispatch.company_id,
                )
            )
            if agent is None or version is None:
                raise DispatchExecutionBlocked(
                    "agent_version_unavailable", "O agente ou sua versão não está disponível."
                )
            actual_mode = select_dispatch_execution_mode(
                requested_mode=dispatch.execution_mode,
                canary_percentage=dispatch.canary_percentage,
                fingerprint=f"{dispatch.objective_fingerprint}:{dispatch.scheduled_for.isoformat()}",
            )
            run = AgentRun(
                company_id=dispatch.company_id,
                agent_id=dispatch.agent_id,
                agent_version_id=dispatch.agent_version_id,
                requested_by_user_id=source.actor_user_id,
                execution_mode=actual_mode,
                status="running",
                request_fingerprint=dispatch.objective_fingerprint,
                planned_tool_keys=list(dispatch.required_tool_keys),
                max_steps=version.max_steps,
                max_runtime_seconds=version.max_runtime_seconds,
                started_at=now,
            )
            database.add(run)
            await database.flush()
            dispatch.status = "processing"
            dispatch.execution_mode = actual_mode
            dispatch.agent_run_id = run.id
            dispatch.attempt_count += 1
            dispatch.started_at = now
            dispatch.reason_code = None
            dispatch.error_code = None
            requested_budget = version.max_cost_per_run_microunits if actual_mode == "live" else 0
            _, reservation = await reserve_agent_budget(
                database,
                company_id=dispatch.company_id,
                agent_id=dispatch.agent_id,
                requested_microunits=requested_budget,
            )
            dispatch.reserved_microunits = reservation
            claimed.append(dispatch.id)
        except (DispatchExecutionBlocked, AgentBudgetExceededError) as exc:
            failed += 1
            dispatch.status = "failed"
            dispatch.error_code = (
                exc.code if isinstance(exc, DispatchExecutionBlocked) else "budget_exceeded"
            )
            dispatch.reason_code = dispatch.error_code
            dispatch.finished_at = now
            if run is not None:
                run.status = "failed"
                run.error_code = dispatch.error_code
                run.finished_at = now
                database.add(
                    AgentRunStep(
                        company_id=run.company_id,
                        agent_id=run.agent_id,
                        agent_run_id=run.id,
                        sequence=1,
                        step_type="runtime",
                        status="failed",
                        summary_code="dispatch.claim.failed",
                        error_code=dispatch.error_code,
                        duration_ms=0,
                        started_at=run.started_at,
                        finished_at=now,
                    )
                )
    await database.commit()
    return claimed, failed


async def _prepare_tools(
    database: AsyncSession,
    *,
    dispatch: AgentRuntimeDispatch,
    permissions: frozenset[str],
    max_steps: int,
    max_runtime_seconds: int,
    started: float,
) -> list[PreparedTool]:
    prepared: list[PreparedTool] = []
    for index, tool_key in enumerate(dispatch.required_tool_keys):
        limit = evaluate_run_limits(
            tool_call_index=index,
            max_steps=max_steps,
            elapsed_seconds=perf_counter() - started,
            max_runtime_seconds=max_runtime_seconds,
        )
        if not limit.allowed:
            raise DispatchExecutionBlocked(limit.error_code or "run_limit", limit.reason)
        tool = await database.scalar(
            select(AgentTool).where(
                AgentTool.company_id == dispatch.company_id,
                AgentTool.agent_id == dispatch.agent_id,
                AgentTool.tool_key == tool_key,
                AgentTool.enabled.is_(True),
            )
        )
        if tool is None:
            raise DispatchExecutionBlocked(
                "tool_unavailable", f"A ferramenta {tool_key} não está disponível."
            )
        arguments = dict(dispatch.tool_arguments.get(tool_key) or {})
        try:
            assert_tool_access(tool, permissions)
            validate_tool_arguments(tool.input_schema, arguments)
        except (ToolAccessError, ToolArgumentsError) as exc:
            raise DispatchExecutionBlocked("tool_preflight_failed", str(exc)) from exc
        autonomy = evaluate_tool_autonomy(
            autonomy_level=(
                await database.scalar(
                    select(AgentVersion.autonomy_level).where(
                        AgentVersion.id == dispatch.agent_version_id,
                        AgentVersion.company_id == dispatch.company_id,
                    )
                )
                or 0
            ),
            risk_level=tool.risk_level,
        )
        if not autonomy.allowed:
            raise DispatchExecutionBlocked("autonomy_denied", autonomy.reason)
        policy = await evaluate_agent_approval_policy(
            database,
            company_id=dispatch.company_id,
            agent_id=dispatch.agent_id,
            tool_key=tool.tool_key,
            arguments=arguments,
        )
        if not policy.allowed:
            raise DispatchExecutionBlocked("policy_denied", policy.reason)
        prepared.append(
            PreparedTool(tool=tool, arguments=arguments, autonomy=autonomy, policy=policy)
        )
    return prepared


def _add_dispatch_trace(
    database: AsyncSession,
    settings: Settings,
    *,
    run: AgentRun,
    prepared: list[PreparedTool],
    tool_runs: list[AgentToolRun],
) -> None:
    now = utc_now()
    runtime_status = (
        "failed"
        if run.status == "failed"
        else "simulated"
        if run.status == "simulated"
        else "completed"
    )
    database.add(
        AgentRunStep(
            company_id=run.company_id,
            agent_id=run.agent_id,
            agent_run_id=run.id,
            sequence=1,
            step_type="runtime",
            status=runtime_status,
            summary_code=f"dispatch.preflight.{runtime_status}",
            error_code=run.error_code,
            duration_ms=run.duration_ms,
            started_at=run.started_at,
            finished_at=run.finished_at or now,
        )
    )
    run_by_key = {item.tool_id: item for item in tool_runs}
    for index, item in enumerate(prepared, start=2):
        tool_run = run_by_key.get(item.tool.id)
        state = tool_run.state if tool_run else "simulated"
        status = {
            "awaiting_confirmation": "awaiting_approval",
            "completed": "completed",
            "failed": "failed",
            "rejected": "blocked",
            "simulated": "simulated",
        }.get(state, "planned")
        database.add(
            AgentRunStep(
                company_id=run.company_id,
                agent_id=run.agent_id,
                agent_run_id=run.id,
                tool_run_id=tool_run.id if tool_run else None,
                sequence=index,
                step_type="tool",
                status=status,
                summary_code=f"tool.execution.{status}",
                tool_key=item.tool.tool_key,
                input_fingerprint=trace_payload_fingerprint(
                    settings,
                    company_id=run.company_id,
                    run_id=run.id,
                    sequence=index,
                    payload=item.arguments,
                ),
                output_fingerprint=(
                    trace_payload_fingerprint(
                        settings,
                        company_id=run.company_id,
                        run_id=run.id,
                        sequence=index,
                        payload=tool_run.result_summary,
                    )
                    if tool_run and tool_run.result_summary
                    else None
                ),
                error_code="tool_execution_failed" if status == "failed" else None,
                duration_ms=0,
                started_at=tool_run.started_at
                if tool_run and tool_run.started_at
                else run.started_at,
                finished_at=tool_run.finished_at if tool_run else run.finished_at,
            )
        )


async def _settle_reservation(database: AsyncSession, dispatch: AgentRuntimeDispatch) -> None:
    if dispatch.reserved_microunits <= 0:
        return
    await settle_agent_budget(
        database,
        company_id=dispatch.company_id,
        agent_id=dispatch.agent_id,
        reserved_microunits=dispatch.reserved_microunits,
        consumed_microunits=0,
    )
    dispatch.reserved_microunits = 0


def is_dispatch_stale(
    *,
    started_at: datetime,
    max_runtime_seconds: int,
    now: datetime,
    grace_seconds: int = 300,
) -> bool:
    deadline = started_at + timedelta(
        seconds=max(1, max_runtime_seconds) + max(0, grace_seconds)
    )
    return deadline < now


async def _reconcile_interrupted_dispatches(
    database: AsyncSession, *, limit: int
) -> int:
    now = utc_now()
    candidates = list(
        await database.scalars(
            select(AgentRuntimeDispatch)
            .where(
                AgentRuntimeDispatch.status == "processing",
                AgentRuntimeDispatch.started_at.is_not(None),
            )
            .order_by(AgentRuntimeDispatch.started_at)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
    )
    reconciled = 0
    for dispatch in candidates:
        run = (
            await database.scalar(
                select(AgentRun).where(
                    AgentRun.id == dispatch.agent_run_id,
                    AgentRun.company_id == dispatch.company_id,
                )
            )
            if dispatch.agent_run_id is not None
            else None
        )
        max_runtime_seconds = run.max_runtime_seconds if run is not None else 120
        if dispatch.started_at is None or not is_dispatch_stale(
            started_at=dispatch.started_at,
            max_runtime_seconds=max_runtime_seconds,
            now=now,
        ):
            continue
        await _settle_reservation(database, dispatch)
        code = "execution_interrupted_manual_review"
        dispatch.status = "failed"
        dispatch.reason_code = code
        dispatch.error_code = code
        dispatch.finished_at = now
        actor_user_id = run.requested_by_user_id if run is not None else None
        if run is not None:
            max_sequence = await database.scalar(
                select(func.max(AgentRunStep.sequence)).where(
                    AgentRunStep.agent_run_id == run.id
                )
            )
            sequence = (max_sequence or 0) + 1
            run.status = "failed"
            run.error_code = code
            run.finished_at = now
            run.duration_ms = max(
                run.duration_ms,
                round(max(0.0, (now - run.started_at).total_seconds()) * 1_000),
            )
            run.step_count = sequence
            database.add(
                AgentRunStep(
                    company_id=run.company_id,
                    agent_id=run.agent_id,
                    agent_run_id=run.id,
                    sequence=sequence,
                    step_type="runtime",
                    status="failed",
                    summary_code="dispatch.interrupted.manual_review",
                    error_code=code,
                    duration_ms=0,
                    started_at=dispatch.started_at,
                    finished_at=now,
                )
            )
        if actor_user_id is not None:
            record_authorization_audit(
                database,
                company_id=dispatch.company_id,
                actor_user_id=actor_user_id,
                action="agent.dispatch.interrupted",
                target_type="agent_runtime_dispatch",
                target_id=dispatch.id,
                details={
                    "agent_id": str(dispatch.agent_id),
                    "agent_run_id": str(dispatch.agent_run_id or ""),
                    "retry_policy": "manual_review_required",
                },
            )
        enqueue_domain_event(
            database,
            DomainEventCreate(
                event_type="agent.dispatch.interrupted",
                company_id=dispatch.company_id,
                actor_user_id=actor_user_id,
                classification="confidential",
                payload={
                    "agent_id": str(dispatch.agent_id),
                    "dispatch_id": str(dispatch.id),
                    "agent_run_id": str(dispatch.agent_run_id or ""),
                    "status": "failed",
                    "reason_code": code,
                    "retry_policy": "manual_review_required",
                },
            ),
        )
        reconciled += 1
    await database.commit()
    return reconciled


async def _execute_claimed_dispatch(
    database: AsyncSession, settings: Settings, *, dispatch_id: UUID
) -> str:
    dispatch = await database.scalar(
        select(AgentRuntimeDispatch).where(
            AgentRuntimeDispatch.id == dispatch_id,
            AgentRuntimeDispatch.status == "processing",
        )
    )
    if dispatch is None or dispatch.agent_run_id is None:
        return "skipped"
    run = await database.scalar(
        select(AgentRun).where(
            AgentRun.id == dispatch.agent_run_id,
            AgentRun.company_id == dispatch.company_id,
        )
    )
    if run is None:
        raise DispatchExecutionBlocked("run_not_found", "A execução vinculada não existe.")
    source = await _dispatch_source(database, dispatch)
    permissions = await _actor_permissions(
        database, company_id=dispatch.company_id, actor_user_id=source.actor_user_id
    )
    if not dispatch.required_tool_keys:
        raise DispatchExecutionBlocked(
            "tools_not_configured", "O despacho não possui ferramentas explicitamente autorizadas."
        )
    started = perf_counter()
    prepared = await _prepare_tools(
        database,
        dispatch=dispatch,
        permissions=permissions,
        max_steps=run.max_steps,
        max_runtime_seconds=run.max_runtime_seconds,
        started=started,
    )
    tool_runs: list[AgentToolRun] = []
    completed: list[str] = []
    states: list[str] = []
    if dispatch.execution_mode == "shadow":
        completed = [item.tool.tool_key for item in prepared]
        states = ["simulated" for _ in prepared]
    else:
        for item in prepared:
            requires_approval = item.requires_approval
            tool_run = AgentToolRun(
                company_id=dispatch.company_id,
                agent_id=dispatch.agent_id,
                agent_version_id=dispatch.agent_version_id,
                agent_run_id=run.id,
                tool_id=item.tool.id,
                requested_by_user_id=source.actor_user_id,
                state="awaiting_confirmation" if requires_approval else "executing",
                arguments=as_summary_object(item.arguments),
                requires_confirmation=requires_approval,
                started_at=None if requires_approval else utc_now(),
            )
            database.add(tool_run)
            await database.flush()
            tool_runs.append(tool_run)
            if requires_approval:
                await create_approval_request(
                    database,
                    company_id=dispatch.company_id,
                    requested_by_user_id=source.actor_user_id,
                    assigned_user_id=item.policy.assigned_user_id,
                    source_type="agent",
                    title=f"Autorizar execução programada: {item.tool.name}",
                    description="A política do agente exige aprovação humana antes da execução.",
                    context={
                        "agent_id": str(dispatch.agent_id),
                        "dispatch_id": str(dispatch.id),
                        "tool_key": item.tool.tool_key,
                        "arguments": tool_run.arguments,
                    },
                    agent_tool_run_id=tool_run.id,
                    expires_at=utc_now() + timedelta(minutes=item.policy.approval_ttl_minutes),
                    reminder_minutes=settings.notification_reminder_minutes,
                )
            else:
                try:
                    remaining_seconds = run.max_runtime_seconds - (perf_counter() - started)
                    if remaining_seconds <= 0:
                        raise TimeoutError
                    async with asyncio.timeout(remaining_seconds):
                        result = await execute_builtin_tool(
                            tool_key=item.tool.tool_key,
                            arguments=item.arguments,
                            company_id=dispatch.company_id,
                            database=database,
                            settings=settings,
                        )
                    tool_run.result_summary = as_summary_object(result)
                    tool_run.state = "completed"
                    completed.append(item.tool.tool_key)
                except (ToolArgumentsError, ToolExecutionError, TimeoutError) as exc:
                    tool_run.state = "failed"
                    tool_run.error_summary = (
                        "A ferramenta excedeu o tempo máximo da execução."
                        if isinstance(exc, TimeoutError)
                        else str(exc)
                    )
                tool_run.finished_at = utc_now()
            states.append(tool_run.state)
    terminal_status = dispatch_status_from_tool_states(
        execution_mode=dispatch.execution_mode, states=states
    )
    run.completed_tool_keys = completed
    run.denied_tool_keys = [
        item.tool.tool_key
        for item, state in zip(prepared, states, strict=True)
        if state in {"failed", "rejected"}
    ]
    run.step_count = len(prepared)
    run.duration_ms = max(0, round((perf_counter() - started) * 1_000))
    run.status = {
        "awaiting_approval": "awaiting_approval",
        "simulated": "simulated",
        "completed": "completed",
        "failed": "failed",
    }[terminal_status]
    run.error_code = "tool_execution_failed" if terminal_status == "failed" else None
    run.finished_at = None if terminal_status == "awaiting_approval" else utc_now()
    dispatch.status = terminal_status
    dispatch.error_code = run.error_code
    dispatch.reason_code = run.error_code
    dispatch.finished_at = run.finished_at
    await _settle_reservation(database, dispatch)
    _add_dispatch_trace(database, settings, run=run, prepared=prepared, tool_runs=tool_runs)
    record_authorization_audit(
        database,
        company_id=dispatch.company_id,
        actor_user_id=source.actor_user_id,
        action=f"agent.dispatch.{terminal_status}",
        target_type="agent_runtime_dispatch",
        target_id=dispatch.id,
        details={
            "agent_id": str(dispatch.agent_id),
            "agent_run_id": str(run.id),
            "execution_mode": dispatch.execution_mode,
            "tool_count": len(prepared),
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=f"agent.dispatch.{terminal_status}",
            company_id=dispatch.company_id,
            actor_user_id=source.actor_user_id,
            classification="confidential",
            payload={
                "agent_id": str(dispatch.agent_id),
                "dispatch_id": str(dispatch.id),
                "agent_run_id": str(run.id),
                "execution_mode": dispatch.execution_mode,
                "status": terminal_status,
            },
        ),
    )
    await database.commit()
    return terminal_status


async def _mark_failed(
    database: AsyncSession, *, dispatch_id: UUID, code: str, settings: Settings
) -> None:
    dispatch = await database.scalar(
        select(AgentRuntimeDispatch).where(AgentRuntimeDispatch.id == dispatch_id)
    )
    if dispatch is None or dispatch.status != "processing":
        return
    dispatch.status = "failed"
    dispatch.error_code = code
    dispatch.reason_code = code
    dispatch.finished_at = utc_now()
    await _settle_reservation(database, dispatch)
    if dispatch.agent_run_id is not None:
        run = await database.scalar(
            select(AgentRun).where(
                AgentRun.id == dispatch.agent_run_id,
                AgentRun.company_id == dispatch.company_id,
            )
        )
        if run is not None:
            run.status = "failed"
            run.error_code = code
            run.finished_at = dispatch.finished_at
            database.add(
                AgentRunStep(
                    company_id=run.company_id,
                    agent_id=run.agent_id,
                    agent_run_id=run.id,
                    sequence=1,
                    step_type="runtime",
                    status="failed",
                    summary_code="dispatch.preflight.failed",
                    error_code=code,
                    duration_ms=0,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                )
            )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.dispatch.failed",
            company_id=dispatch.company_id,
            classification="confidential",
            payload={"dispatch_id": str(dispatch.id), "error_code": code},
        ),
    )
    await database.commit()


async def execute_ready_agent_dispatches(
    *, settings: Settings | None = None, limit: int = 20
) -> dict[str, int]:
    active_settings = settings or get_settings()
    resources = create_resources(active_settings)
    result = {
        "reconciled": 0,
        "claimed": 0,
        "completed": 0,
        "simulated": 0,
        "awaiting_approval": 0,
        "failed": 0,
        "skipped": 0,
    }
    try:
        async with resources.sessions() as database:
            reconciled = await _reconcile_interrupted_dispatches(
                database, limit=max(1, min(limit, 100))
            )
            dispatch_ids, claim_failures = await _claim_ready_dispatches(
                database, active_settings, limit=max(1, min(limit, 100))
            )
        result["reconciled"] = reconciled
        result["claimed"] = len(dispatch_ids)
        result["failed"] += reconciled + claim_failures
        for dispatch_id in dispatch_ids:
            try:
                async with resources.sessions() as database:
                    status = await _execute_claimed_dispatch(
                        database, active_settings, dispatch_id=dispatch_id
                    )
                result[status] += 1
            except DispatchExecutionBlocked as exc:
                async with resources.sessions() as database:
                    await _mark_failed(
                        database, dispatch_id=dispatch_id, code=exc.code, settings=active_settings
                    )
                result["failed"] += 1
            except Exception:
                get_logger(component="agent_dispatch").exception(
                    "agent_dispatch_execution_failed", dispatch_id=str(dispatch_id)
                )
                async with resources.sessions() as database:
                    await _mark_failed(
                        database,
                        dispatch_id=dispatch_id,
                        code="unexpected_execution_error",
                        settings=active_settings,
                    )
                result["failed"] += 1
        return result
    finally:
        await resources.close()


def execute_ready_agent_dispatches_sync(limit: int = 20) -> dict[str, int]:
    return asyncio.run(execute_ready_agent_dispatches(limit=limit))
