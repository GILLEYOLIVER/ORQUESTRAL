from __future__ import annotations

import hashlib
import hmac
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.agents.models import AgentRun, AgentRunStep


def trace_payload_fingerprint(
    settings: Settings,
    *,
    company_id: UUID,
    run_id: UUID,
    sequence: int,
    payload: Any,
) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    message = f"agent-trace:{company_id}:{run_id}:{sequence}:{serialized}".encode()
    return hmac.new(settings.encryption_key.encode(), message, hashlib.sha256).hexdigest()


def build_agent_run_steps(
    settings: Settings,
    *,
    run: AgentRun,
    tool_arguments: Sequence[Mapping[str, Any]] = (),
    tool_outputs: Sequence[Any | None] = (),
    tool_run_ids: Mapping[str, UUID] | None = None,
) -> list[AgentRunStep]:
    provider_status = "completed"
    provider_summary = "provider.response.completed"
    if run.error_code == "provider_timeout" or run.status == "timed_out":
        provider_status = "timed_out"
        provider_summary = "provider.response.timed_out"
    elif run.error_code == "provider_error" or (
        run.status == "failed" and not run.planned_tool_keys
    ):
        provider_status = "failed"
        provider_summary = "provider.response.failed"

    steps = [
        AgentRunStep(
            company_id=run.company_id,
            agent_id=run.agent_id,
            agent_run_id=run.id,
            sequence=1,
            step_type="provider",
            status=provider_status,
            summary_code=provider_summary,
            error_code=run.error_code if provider_status != "completed" else None,
            duration_ms=run.duration_ms if not run.planned_tool_keys else 0,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )
    ]

    completed = Counter(run.completed_tool_keys)
    denied = Counter(run.denied_tool_keys)
    tool_run_ids = tool_run_ids or {}
    for index, tool_key in enumerate(run.planned_tool_keys):
        if completed[tool_key] > 0:
            completed[tool_key] -= 1
            step_status = "simulated" if run.execution_mode != "live" else "completed"
            summary_code = (
                "tool.execution.simulated"
                if step_status == "simulated"
                else "tool.execution.completed"
            )
            error_code = None
        elif denied[tool_key] > 0:
            denied[tool_key] -= 1
            step_status = "blocked"
            summary_code = "tool.execution.blocked"
            error_code = run.error_code or "tool_blocked"
        elif run.status == "awaiting_approval":
            step_status = "awaiting_approval"
            summary_code = "tool.execution.awaiting_approval"
            error_code = None
        elif run.status in {"failed", "timed_out"}:
            step_status = "failed"
            summary_code = "tool.execution.failed"
            error_code = run.error_code or "tool_execution_failed"
        else:
            step_status = "planned"
            summary_code = "tool.execution.planned"
            error_code = None

        sequence = index + 2
        input_fingerprint = (
            trace_payload_fingerprint(
                settings,
                company_id=run.company_id,
                run_id=run.id,
                sequence=sequence,
                payload=tool_arguments[index],
            )
            if index < len(tool_arguments)
            else None
        )
        output_fingerprint = (
            trace_payload_fingerprint(
                settings,
                company_id=run.company_id,
                run_id=run.id,
                sequence=sequence,
                payload=tool_outputs[index],
            )
            if index < len(tool_outputs) and tool_outputs[index] is not None
            else None
        )
        steps.append(
            AgentRunStep(
                company_id=run.company_id,
                agent_id=run.agent_id,
                agent_run_id=run.id,
                tool_run_id=tool_run_ids.get(tool_key),
                sequence=sequence,
                step_type="tool",
                status=step_status,
                summary_code=summary_code,
                tool_key=tool_key,
                input_fingerprint=input_fingerprint,
                output_fingerprint=output_fingerprint,
                error_code=error_code,
                duration_ms=0,
                started_at=run.started_at,
                finished_at=run.finished_at,
            )
        )
    return steps


def add_agent_run_steps(
    database: AsyncSession,
    settings: Settings,
    *,
    run: AgentRun,
    tool_arguments: Sequence[Mapping[str, Any]] = (),
    tool_outputs: Sequence[Any | None] = (),
    tool_run_ids: Mapping[str, UUID] | None = None,
) -> list[AgentRunStep]:
    steps = build_agent_run_steps(
        settings,
        run=run,
        tool_arguments=tool_arguments,
        tool_outputs=tool_outputs,
        tool_run_ids=tool_run_ids,
    )
    database.add_all(steps)
    return steps
