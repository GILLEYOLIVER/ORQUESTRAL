from __future__ import annotations

import asyncio
import socket
from datetime import timedelta
from time import perf_counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.resources import create_resources
from app.core.security import utc_now
from app.modules.agents.coordination import coordination_fingerprint
from app.modules.agents.coordination_models import (
    AgentDelegation,
    AgentDelegationPayload,
    AgentTaskContract,
)
from app.modules.agents.coordination_payload import decrypt_delegation_objective
from app.modules.agents.governance import active_agent_version, evaluate_tool_autonomy
from app.modules.agents.models import Agent, AgentDataPolicy, AgentRun, AgentTool
from app.modules.agents.providers.base import (
    LanguageModelProviderError,
    ModelMessage,
    ToolDefinition,
)
from app.modules.agents.providers.factory import create_language_model_provider
from app.modules.agents.security import (
    AgentDataPolicyViolation,
    assert_provider_data_policy,
    protect_provider_text,
    scan_prompt_injection,
)
from app.modules.agents.tools import (
    ToolAccessError,
    ToolArgumentsError,
    ToolExecutionError,
    assert_tool_access,
    execute_builtin_tool,
    validate_tool_arguments,
)
from app.modules.authorization.models import Permission, RolePermission
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.users.models import CompanyUser


async def process_delegation(delegation_id: UUID, *, settings: Settings) -> dict[str, str | int]:
    resources = create_resources(settings)
    try:
        async with resources.sessions() as database:
            delegation = await database.scalar(
                select(AgentDelegation)
                .where(AgentDelegation.id == delegation_id)
                .with_for_update(skip_locked=True)
            )
            if delegation is None:
                return {"status": "not_found", "delegation_id": str(delegation_id)}
            if delegation.status != "queued":
                return {"status": delegation.status, "delegation_id": str(delegation.id)}
            payload = await database.scalar(
                select(AgentDelegationPayload).where(
                    AgentDelegationPayload.delegation_id == delegation.id,
                    AgentDelegationPayload.company_id == delegation.company_id,
                )
            )
            now = utc_now()
            if payload is None or payload.encrypted_objective is None or payload.expires_at <= now:
                delegation.status = "failed"
                delegation.last_error_code = "payload_expired"
                delegation.finished_at = now
                if payload is not None:
                    payload.encrypted_objective = None
                    payload.destroyed_at = now
                await database.commit()
                return {"status": "failed", "delegation_id": str(delegation.id)}
            objective = decrypt_delegation_objective(
                settings,
                company_id=delegation.company_id,
                delegation_id=delegation.id,
                encrypted=payload.encrypted_objective,
            )
            delegation.status = "in_progress"
            delegation.attempt_count += 1
            delegation.claimed_by = f"{socket.gethostname()}:{id(asyncio.current_task())}"
            delegation.started_at = now
            delegation.lease_expires_at = now + timedelta(minutes=5)
            await database.commit()

            contract = await database.scalar(
                select(AgentTaskContract).where(
                    AgentTaskContract.id == delegation.contract_id,
                    AgentTaskContract.company_id == delegation.company_id,
                    AgentTaskContract.status == "active",
                )
            )
            agent = await database.scalar(
                select(Agent).where(
                    Agent.id == delegation.assigned_agent_id,
                    Agent.company_id == delegation.company_id,
                    Agent.status == "active",
                )
            )
            policy = await database.scalar(
                select(AgentDataPolicy).where(
                    AgentDataPolicy.agent_id == delegation.assigned_agent_id,
                    AgentDataPolicy.company_id == delegation.company_id,
                )
            )
            if contract is None or agent is None or policy is None:
                return await _fail(
                    database, delegation, payload, "coordination_configuration_missing"
                )
            membership = await database.scalar(
                select(CompanyUser).where(
                    CompanyUser.company_id == delegation.company_id,
                    CompanyUser.user_id == delegation.requested_by_user_id,
                    CompanyUser.status == "active",
                )
            )
            if membership is None:
                return await _fail(database, delegation, payload, "requester_access_revoked")
            permissions = frozenset(
                await database.scalars(
                    select(Permission.code)
                    .join(RolePermission, RolePermission.permission_id == Permission.id)
                    .where(RolePermission.role_id == membership.role_id)
                )
            )
            if "agents.execute" not in permissions:
                return await _fail(database, delegation, payload, "requester_permission_revoked")
            version = await active_agent_version(
                database, agent=agent, company_id=delegation.company_id
            )
            if version is None:
                return await _fail(database, delegation, payload, "agent_version_missing")
            try:
                assert_provider_data_policy(
                    policy,
                    provider=version.provider,
                    includes_knowledge=False,
                )
            except AgentDataPolicyViolation:
                return await _fail(database, delegation, payload, "provider_policy_denied")
            if scan_prompt_injection(objective).detected:
                return await _fail(database, delegation, payload, "prompt_injection_blocked")
            tools = (
                await database.scalars(
                    select(AgentTool).where(
                        AgentTool.agent_id == agent.id,
                        AgentTool.company_id == delegation.company_id,
                        AgentTool.enabled.is_(True),
                        AgentTool.tool_key.in_(contract.allowed_tool_keys),
                    )
                )
            ).all()
            provider_tools = [
                ToolDefinition(
                    key=tool.tool_key,
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.input_schema,
                )
                for tool in tools
            ]
            protected_instructions = protect_provider_text(
                policy, provider=version.provider, text=version.instructions
            )[0]
            protected_objective = protect_provider_text(
                policy, provider=version.provider, text=objective
            )[0]
            started = perf_counter()
            try:
                provider = create_language_model_provider(version.provider, settings)
                async with asyncio.timeout(
                    min(version.max_runtime_seconds, contract.deadline_seconds)
                ):
                    result = await provider.generate(
                        messages=[
                            ModelMessage(role="system", content=protected_instructions),
                            ModelMessage(role="user", content=protected_objective),
                        ],
                        tools=provider_tools,
                        model=version.model,
                        temperature=version.temperature,
                        max_output_tokens=version.max_output_tokens,
                    )
                    usage = await provider.calculate_usage(result)
            except (LanguageModelProviderError, TimeoutError):
                return await _fail(database, delegation, payload, "provider_failure")
            completed: list[str] = []
            denied: list[str] = []
            tool_by_key = {tool.tool_key: tool for tool in tools}
            error_code: str | None = None
            for index, call in enumerate(result.tool_calls):
                if index >= contract.max_steps:
                    denied.append(call.key)
                    error_code = "contract_steps_exceeded"
                    continue
                tool = tool_by_key.get(call.key)
                if tool is None:
                    denied.append(call.key)
                    error_code = "contract_tool_denied"
                    continue
                autonomy = evaluate_tool_autonomy(
                    autonomy_level=version.autonomy_level, risk_level=tool.risk_level
                )
                if not autonomy.allowed or autonomy.requires_approval:
                    denied.append(call.key)
                    error_code = "human_approval_required"
                    continue
                try:
                    assert_tool_access(tool, permissions)
                    validate_tool_arguments(tool.input_schema, call.arguments)
                    await execute_builtin_tool(
                        tool_key=tool.tool_key,
                        arguments=call.arguments,
                        company_id=delegation.company_id,
                        database=database,
                        settings=settings,
                    )
                    completed.append(call.key)
                except (ToolAccessError, ToolArgumentsError, ToolExecutionError):
                    denied.append(call.key)
                    error_code = "tool_execution_failed"
            duration_ms = max(0, round((perf_counter() - started) * 1000))
            if usage.cost_microunits > contract.max_cost_microunits:
                error_code = "contract_cost_exceeded"
            run_status = "failed" if error_code else "completed"
            agent_run = AgentRun(
                company_id=delegation.company_id,
                agent_id=agent.id,
                agent_version_id=version.id,
                requested_by_user_id=delegation.requested_by_user_id,
                execution_mode="live",
                status=run_status,
                request_fingerprint=delegation.objective_fingerprint,
                planned_tool_keys=[call.key for call in result.tool_calls],
                completed_tool_keys=completed,
                denied_tool_keys=denied,
                error_code=error_code,
                step_count=min(len(result.tool_calls), contract.max_steps),
                total_tokens=usage.total_tokens,
                cost_microunits=usage.cost_microunits,
                duration_ms=duration_ms,
                max_steps=contract.max_steps,
                max_runtime_seconds=min(version.max_runtime_seconds, contract.deadline_seconds),
                finished_at=utc_now(),
            )
            database.add(agent_run)
            delegation.status = run_status
            delegation.last_error_code = error_code
            delegation.consumed_cost_microunits = usage.cost_microunits
            delegation.result_fingerprint = coordination_fingerprint(
                company_id=delegation.company_id,
                value=result.content + "|" + ",".join(completed),
            )
            delegation.finished_at = utc_now()
            delegation.lease_expires_at = None
            payload.encrypted_objective = None
            payload.destroyed_at = utc_now()
            record_authorization_audit(
                database,
                company_id=delegation.company_id,
                actor_user_id=delegation.requested_by_user_id,
                action=f"agent.delegation.{run_status}",
                target_type="agent_delegation",
                target_id=delegation.id,
                details={
                    "agent_run_id": str(agent_run.id),
                    "status": run_status,
                    "error_code": error_code,
                },
            )
            enqueue_domain_event(
                database,
                DomainEventCreate(
                    event_type=f"agent.delegation.{run_status}",
                    company_id=delegation.company_id,
                    actor_user_id=delegation.requested_by_user_id,
                    classification="confidential",
                    payload={
                        "delegation_id": str(delegation.id),
                        "agent_run_id": str(agent_run.id),
                        "status": run_status,
                        "error_code": error_code,
                    },
                ),
            )
            await database.commit()
            return {
                "status": run_status,
                "delegation_id": str(delegation.id),
                "completed_tools": len(completed),
            }
    finally:
        await resources.close()


async def _fail(
    database: AsyncSession,
    delegation: AgentDelegation,
    payload: AgentDelegationPayload,
    error_code: str,
) -> dict[str, str | int]:
    delegation.status = "failed"
    delegation.last_error_code = error_code
    delegation.finished_at = utc_now()
    delegation.lease_expires_at = None
    payload.encrypted_objective = None
    payload.destroyed_at = utc_now()
    await database.commit()
    return {"status": "failed", "delegation_id": str(delegation.id)}


async def maintain_delegations(*, settings: Settings) -> dict[str, int]:
    resources = create_resources(settings)
    expired = recovered = 0
    try:
        async with resources.sessions() as database:
            now = utc_now()
            rows = list(
                await database.scalars(
                    select(AgentDelegation).where(
                        AgentDelegation.status.in_(("queued", "in_progress"))
                    )
                )
            )
            for delegation in rows:
                payload = await database.scalar(
                    select(AgentDelegationPayload).where(
                        AgentDelegationPayload.delegation_id == delegation.id
                    )
                )
                if delegation.due_at <= now:
                    delegation.status = "failed"
                    delegation.last_error_code = "delegation_expired"
                    delegation.finished_at = now
                    delegation.lease_expires_at = None
                    if payload:
                        payload.encrypted_objective = None
                        payload.destroyed_at = now
                    expired += 1
                elif (
                    delegation.status == "in_progress"
                    and delegation.lease_expires_at
                    and delegation.lease_expires_at <= now
                ):
                    delegation.status = "queued"
                    delegation.claimed_by = None
                    delegation.lease_expires_at = None
                    recovered += 1
            await database.commit()
            return {"expired": expired, "recovered": recovered}
    finally:
        await resources.close()


def process_delegation_sync(delegation_id: str) -> dict[str, str | int]:
    return asyncio.run(process_delegation(UUID(delegation_id), settings=get_settings()))


def maintain_delegations_sync() -> dict[str, int]:
    return asyncio.run(maintain_delegations(settings=get_settings()))
