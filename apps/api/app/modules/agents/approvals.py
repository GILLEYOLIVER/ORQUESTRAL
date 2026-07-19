from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import utc_now
from app.modules.agents.models import AgentTool, AgentToolRun
from app.modules.agents.tools import (
    ToolAccessError,
    ToolArgumentsError,
    ToolExecutionError,
    assert_tool_access,
    execute_builtin_tool,
    validate_tool_arguments,
)
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
    return run
