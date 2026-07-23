from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import utc_now
from app.modules.agents.models import AgentRun, AgentRunStep, AgentTool, AgentToolRun
from app.modules.agents.runtime_models import AgentRuntimeDispatch
from app.modules.agents.tools import (
    ToolAccessError,
    ToolArgumentsError,
    ToolExecutionError,
    assert_tool_access,
    execute_builtin_tool,
    validate_tool_arguments,
)
from app.modules.agents.trace import trace_payload_fingerprint
from app.modules.authorization.service import record_authorization_audit
from app.modules.notifications.service import resolve_linked_agent_approval
from app.modules.workflows.definition import as_summary_object


async def decide_agent_tool_run(
    database: AsyncSession,
    *,
    run_id: UUID,
    company_id: UUID,
    actor_user_id: UUID,
    permissions: frozenset[str],
    decision: Literal["approved", "rejected"],
    settings: Settings,
    sync_approval: bool = True,
) -> AgentToolRun:
    run = await database.scalar(
        select(AgentToolRun).where(
            AgentToolRun.id == run_id,
            AgentToolRun.company_id == company_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Ação não encontrada nesta empresa.")
    if run.state != "awaiting_confirmation":
        raise HTTPException(status_code=409, detail="Esta ação já recebeu uma decisão.")
    tool = await database.scalar(
        select(AgentTool).where(
            AgentTool.id == run.tool_id,
            AgentTool.company_id == company_id,
        )
    )
    if tool is None:
        raise HTTPException(status_code=404, detail="Ferramenta da ação não encontrada.")
    now = utc_now()
    if decision == "rejected":
        run.state = "rejected"
        run.rejected_by_user_id = actor_user_id
        run.rejected_at = now
        run.finished_at = now
    else:
        run.approved_by_user_id = actor_user_id
        run.approved_at = now
        try:
            assert_tool_access(tool, permissions)
            validate_tool_arguments(tool.input_schema, run.arguments)
            run.state = "executing"
            run.started_at = now
            result = await execute_builtin_tool(
                tool_key=tool.tool_key,
                arguments=run.arguments,
                company_id=company_id,
                database=database,
                settings=settings,
            )
            run.result_summary = as_summary_object(result)
            run.state = "completed"
        except (ToolAccessError, ToolArgumentsError, ToolExecutionError) as exc:
            run.state = "failed"
            run.error_summary = str(exc)
        run.finished_at = utc_now()
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action=f"agent.tool.{run.state}",
        target_type="agent_tool_run",
        target_id=run.id,
        details={"tool_key": tool.tool_key, "decision": decision},
    )
    if sync_approval:
        await resolve_linked_agent_approval(
            database,
            company_id=company_id,
            agent_tool_run_id=run.id,
            actor_user_id=actor_user_id,
            decision=decision,
        )
    dispatch = await database.scalar(
        select(AgentRuntimeDispatch).where(
            AgentRuntimeDispatch.company_id == company_id,
            AgentRuntimeDispatch.agent_run_id == run.agent_run_id,
        )
    )
    if dispatch is not None and run.agent_run_id is not None:
        trace_step = await database.scalar(
            select(AgentRunStep).where(
                AgentRunStep.company_id == company_id,
                AgentRunStep.tool_run_id == run.id,
            )
        )
        if trace_step is not None:
            trace_step.status = (
                "completed"
                if run.state == "completed"
                else "blocked"
                if run.state == "rejected"
                else "failed"
            )
            trace_step.summary_code = f"tool.execution.{trace_step.status}"
            trace_step.error_code = (
                None
                if run.state == "completed"
                else "tool_rejected"
                if run.state == "rejected"
                else "tool_execution_failed"
            )
            trace_step.output_fingerprint = (
                trace_payload_fingerprint(
                    settings,
                    company_id=company_id,
                    run_id=run.agent_run_id,
                    sequence=trace_step.sequence,
                    payload=run.result_summary,
                )
                if run.result_summary
                else None
            )
            trace_step.finished_at = run.finished_at
        linked_runs = list(
            await database.scalars(
                select(AgentToolRun).where(
                    AgentToolRun.company_id == company_id,
                    AgentToolRun.agent_run_id == run.agent_run_id,
                )
            )
        )
        states = [item.state for item in linked_runs]
        if any(state in {"failed", "rejected"} for state in states):
            dispatch.status = "failed"
            dispatch.error_code = (
                "tool_rejected" if "rejected" in states else "tool_execution_failed"
            )
        elif states and all(state == "completed" for state in states):
            dispatch.status = "completed"
            dispatch.error_code = None
        if dispatch.status in {"failed", "completed"}:
            dispatch.reason_code = dispatch.error_code
            dispatch.finished_at = utc_now()
            agent_run = await database.scalar(
                select(AgentRun).where(
                    AgentRun.id == run.agent_run_id,
                    AgentRun.company_id == company_id,
                )
            )
            if agent_run is not None:
                agent_run.status = dispatch.status
                agent_run.error_code = dispatch.error_code
                agent_run.finished_at = dispatch.finished_at
    return run
