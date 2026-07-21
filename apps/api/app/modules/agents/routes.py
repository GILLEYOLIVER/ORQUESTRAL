from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.agents.approvals import decide_agent_tool_run
from app.modules.agents.governance import (
    AgentBudgetExceededError,
    active_agent_version,
    agent_request_fingerprint,
    agent_version_payload,
    evaluate_run_limits,
    evaluate_tool_autonomy,
    reserve_agent_budget,
    settle_agent_budget,
    version_checksum,
)
from app.modules.agents.models import (
    Agent,
    AgentBudget,
    AgentConversation,
    AgentDataPolicy,
    AgentMessage,
    AgentRun,
    AgentSecurityEvent,
    AgentTool,
    AgentToolRun,
    AgentUsageRecord,
    AgentVersion,
)
from app.modules.agents.providers.base import (
    LanguageModelProviderError,
    ModelMessage,
    ToolDefinition,
)
from app.modules.agents.providers.factory import create_language_model_provider
from app.modules.agents.schemas import (
    AgentBudgetResponse,
    AgentBudgetUpdate,
    AgentChatRequest,
    AgentChatResponse,
    AgentConversationCreate,
    AgentConversationResponse,
    AgentCreate,
    AgentDataPolicyResponse,
    AgentDataPolicyUpdate,
    AgentMessageResponse,
    AgentProviderStatusResponse,
    AgentResponse,
    AgentRunResponse,
    AgentSecurityEventResponse,
    AgentToolCatalogResponse,
    AgentToolDecision,
    AgentToolResponse,
    AgentToolRunResponse,
    AgentToolsUpdate,
    AgentUpdate,
    AgentUsageResponse,
    AgentVersionCreate,
    AgentVersionResponse,
)
from app.modules.agents.security import (
    AgentDataPolicyViolation,
    assert_provider_data_policy,
    protect_provider_text,
    scan_prompt_injection,
)
from app.modules.agents.tools import (
    BUILTIN_TOOLS,
    TOOL_CATALOG,
    ToolAccessError,
    ToolArgumentsError,
    ToolExecutionError,
    assert_tool_access,
    execute_builtin_tool,
    validate_tool_arguments,
)
from app.modules.authorization.service import record_authorization_audit
from app.modules.billing.service import UsageMetric, enforce_limit, record_usage
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.knowledge.models import KnowledgeBase
from app.modules.knowledge.processing import search_knowledge
from app.modules.notifications.service import create_approval_request
from app.modules.workflows.definition import as_summary_object

router = APIRouter(prefix="/agents", tags=["agents"])
CanViewAgents = Annotated[Principal, Depends(require_permission("agents.view"))]
CanCreateAgents = Annotated[Principal, Depends(require_permission("agents.create"))]
CanConfigureAgents = Annotated[Principal, Depends(require_permission("agents.configure"))]
CanExecuteAgents = Annotated[Principal, Depends(require_permission("agents.execute"))]


def _agent_response(agent: Agent) -> AgentResponse:
    return AgentResponse.model_validate(agent, from_attributes=True)


def _conversation_response(conversation: AgentConversation) -> AgentConversationResponse:
    return AgentConversationResponse.model_validate(conversation, from_attributes=True)


def _message_response(message: AgentMessage) -> AgentMessageResponse:
    return AgentMessageResponse.model_validate(message, from_attributes=True)


def _tool_response(tool: AgentTool) -> AgentToolResponse:
    return AgentToolResponse.model_validate(tool, from_attributes=True)


def _version_response(version: AgentVersion) -> AgentVersionResponse:
    return AgentVersionResponse.model_validate(version, from_attributes=True)


def _budget_response(budget: AgentBudget) -> AgentBudgetResponse:
    return AgentBudgetResponse.model_validate(budget, from_attributes=True)


def _run_response(run: AgentRun) -> AgentRunResponse:
    return AgentRunResponse.model_validate(run, from_attributes=True)


def _data_policy_response(policy: AgentDataPolicy) -> AgentDataPolicyResponse:
    return AgentDataPolicyResponse.model_validate(policy, from_attributes=True)


def _security_event_response(event: AgentSecurityEvent) -> AgentSecurityEventResponse:
    return AgentSecurityEventResponse.model_validate(event, from_attributes=True)


async def _data_policy(
    database: DatabaseSession, *, agent_id: UUID, company_id: UUID
) -> AgentDataPolicy:
    policy = await database.scalar(
        select(AgentDataPolicy).where(
            AgentDataPolicy.agent_id == agent_id, AgentDataPolicy.company_id == company_id
        )
    )
    if policy is None:
        raise HTTPException(status_code=409, detail="Política de dados do agente não configurada.")
    return policy


async def _budget(database: DatabaseSession, *, agent_id: UUID, company_id: UUID) -> AgentBudget:
    budget = await database.scalar(
        select(AgentBudget).where(
            AgentBudget.agent_id == agent_id, AgentBudget.company_id == company_id
        )
    )
    if budget is None:
        raise HTTPException(status_code=404, detail="Orçamento do agente não encontrado.")
    return budget


async def _next_agent_version(database: DatabaseSession, agent_id: UUID) -> int:
    current = await database.scalar(
        select(func.max(AgentVersion.version)).where(AgentVersion.agent_id == agent_id)
    )
    return int(current or 0) + 1


async def _publish_agent_version(
    database: DatabaseSession,
    *,
    agent: Agent,
    version: AgentVersion,
    actor_user_id: UUID,
) -> None:
    published = (
        await database.scalars(
            select(AgentVersion).where(
                AgentVersion.agent_id == agent.id,
                AgentVersion.company_id == agent.company_id,
                AgentVersion.status == "published",
                AgentVersion.id != version.id,
            )
        )
    ).all()
    for previous in published:
        previous.status = "retired"
    version.status = "published"
    version.published_by_user_id = actor_user_id
    version.published_at = utc_now()
    for field in (
        "instructions",
        "provider",
        "model",
        "temperature",
        "max_input_tokens",
        "max_output_tokens",
        "memory_enabled",
        "knowledge_base_id",
    ):
        setattr(agent, field, getattr(version, field))
    agent.active_version_id = version.id
    agent.updated_at = utc_now()


async def _agent(database: DatabaseSession, *, agent_id: UUID, company_id: UUID) -> Agent:
    agent = await database.scalar(
        select(Agent).where(Agent.id == agent_id, Agent.company_id == company_id)
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Agente não encontrado nesta empresa.")
    return agent


async def _conversation(
    database: DatabaseSession, *, conversation_id: UUID, agent_id: UUID, company_id: UUID
) -> AgentConversation:
    conversation = await database.scalar(
        select(AgentConversation).where(
            AgentConversation.id == conversation_id,
            AgentConversation.agent_id == agent_id,
            AgentConversation.company_id == company_id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada para este agente.")
    return conversation


async def _tool_run_response(database: DatabaseSession, run: AgentToolRun) -> AgentToolRunResponse:
    tool = await database.scalar(select(AgentTool).where(AgentTool.id == run.tool_id))
    if tool is None:
        raise HTTPException(status_code=500, detail="Ferramenta da ação não encontrada.")
    return AgentToolRunResponse(
        id=run.id,
        agent_id=run.agent_id,
        conversation_id=run.conversation_id,
        tool_key=tool.tool_key,
        tool_name=tool.name,
        state=run.state,
        requires_confirmation=run.requires_confirmation,
        result_summary=run.result_summary,
        error_summary=run.error_summary,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


@router.get("/providers/status", response_model=list[AgentProviderStatusResponse])
async def provider_status(
    principal: CanViewAgents, settings: RequestSettings
) -> list[AgentProviderStatusResponse]:
    get_request_context(principal)
    configured = bool((settings.ai_provider_api_key or "").strip())
    return [
        AgentProviderStatusResponse(
            provider="local", configured=True, message="Provedor local seguro disponível."
        ),
        AgentProviderStatusResponse(
            provider="openai_compatible",
            configured=configured,
            message="Provedor externo configurado."
            if configured
            else "Provedor externo sem credencial administrativa.",
        ),
    ]


@router.get("/tools/catalog", response_model=list[AgentToolCatalogResponse])
async def tool_catalog(principal: CanConfigureAgents) -> list[AgentToolCatalogResponse]:
    get_request_context(principal)
    return [
        AgentToolCatalogResponse(
            key=tool.key,
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_schema,
            required_permission=tool.required_permission,
            is_sensitive=tool.is_sensitive,
        )
        for tool in BUILTIN_TOOLS
    ]


@router.get("/actions/pending", response_model=list[AgentToolRunResponse])
async def pending_actions(
    principal: CanExecuteAgents, database: DatabaseSession
) -> list[AgentToolRunResponse]:
    context = get_request_context(principal)
    runs = (
        await database.scalars(
            select(AgentToolRun)
            .where(
                AgentToolRun.company_id == context.company_id,
                AgentToolRun.state == "awaiting_confirmation",
            )
            .order_by(AgentToolRun.created_at.desc())
            .limit(100)
        )
    ).all()
    return [await _tool_run_response(database, run) for run in runs]


@router.post("/actions/{run_id}/decision", response_model=AgentToolRunResponse)
async def decide_action(
    run_id: UUID,
    payload: AgentToolDecision,
    principal: CanExecuteAgents,
    database: DatabaseSession,
    settings: RequestSettings,
) -> AgentToolRunResponse:
    context = get_request_context(principal)
    run = await decide_agent_tool_run(
        database,
        run_id=run_id,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        permissions=principal.permissions,
        decision=payload.decision,
        settings=settings,
    )
    await database.commit()
    await database.refresh(run)
    return await _tool_run_response(database, run)


@router.get("/usage", response_model=list[AgentUsageResponse])
async def list_usage(
    principal: CanViewAgents, database: DatabaseSession
) -> list[AgentUsageResponse]:
    context = get_request_context(principal)
    records = (
        await database.scalars(
            select(AgentUsageRecord)
            .where(AgentUsageRecord.company_id == context.company_id)
            .order_by(AgentUsageRecord.created_at.desc())
            .limit(200)
        )
    ).all()
    return [AgentUsageResponse.model_validate(record, from_attributes=True) for record in records]


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    principal: CanViewAgents,
    database: DatabaseSession,
    include_inactive: bool = Query(default=False),
) -> list[AgentResponse]:
    context = get_request_context(principal)
    statement = select(Agent).where(Agent.company_id == context.company_id)
    if not include_inactive:
        statement = statement.where(Agent.status == "active")
    agents = (await database.scalars(statement.order_by(Agent.created_at.desc()))).all()
    return [_agent_response(agent) for agent in agents]


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    principal: CanCreateAgents,
    database: DatabaseSession,
    settings: RequestSettings,
) -> AgentResponse:
    context = get_request_context(principal)
    await enforce_limit(
        database,
        company_id=context.company_id,
        metric=UsageMetric.AGENTS,
        enforcement_enabled=settings.billing_enforcement_enabled,
    )
    agent = Agent(
        company_id=context.company_id, created_by_user_id=context.user_id, **payload.model_dump()
    )
    database.add(agent)
    await database.flush()
    version_payload = agent_version_payload(agent)
    version = AgentVersion(
        company_id=context.company_id,
        agent_id=agent.id,
        version=1,
        status="published",
        created_by_user_id=context.user_id,
        published_by_user_id=context.user_id,
        published_at=utc_now(),
        checksum=version_checksum(version_payload),
        **version_payload,
    )
    database.add(version)
    await database.flush()
    agent.active_version_id = version.id
    now = utc_now()
    next_month = (
        now.replace(year=now.year + 1, month=1, day=1)
        if now.month == 12
        else now.replace(month=now.month + 1, day=1)
    )
    database.add(
        AgentBudget(
            company_id=context.company_id,
            agent_id=agent.id,
            cycle_started_at=now,
            cycle_ends_at=next_month,
        )
    )
    is_external = agent.provider != "local"
    database.add(
        AgentDataPolicy(
            company_id=context.company_id,
            agent_id=agent.id,
            allowed_provider_keys=[agent.provider],
            external_processing_enabled=is_external,
            allow_message_egress=is_external,
            allow_knowledge_egress=is_external,
            redact_sensitive_data=True,
            max_data_classification="confidential",
        )
    )
    definition = TOOL_CATALOG["orkestral.company.summary"]
    database.add(
        AgentTool(
            company_id=context.company_id,
            agent_id=agent.id,
            tool_key=definition.key,
            name=definition.name,
            description=definition.description,
            input_schema=definition.input_schema,
            required_permission=definition.required_permission,
            risk_level=definition.risk_level,
            is_sensitive=definition.is_sensitive,
        )
    )
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.created",
        target_type="agent",
        target_id=agent.id,
        details={"name": agent.name, "provider": agent.provider, "model": agent.model},
    )
    await record_usage(
        database,
        company_id=context.company_id,
        metric=UsageMetric.AGENTS,
        quantity=1,
        metadata={"agent_id": str(agent.id)},
        idempotency_key=f"agent:{agent.id}",
    )
    await database.commit()
    await database.refresh(agent)
    return _agent_response(agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID, principal: CanViewAgents, database: DatabaseSession
) -> AgentResponse:
    context = get_request_context(principal)
    return _agent_response(await _agent(database, agent_id=agent_id, company_id=context.company_id))


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID, payload: AgentUpdate, principal: CanConfigureAgents, database: DatabaseSession
) -> AgentResponse:
    context = get_request_context(principal)
    agent = await _agent(database, agent_id=agent_id, company_id=context.company_id)
    if "knowledge_base_id" in payload.model_fields_set and payload.knowledge_base_id is not None:
        knowledge_base = await database.scalar(
            select(KnowledgeBase).where(
                KnowledgeBase.id == payload.knowledge_base_id,
                KnowledgeBase.company_id == context.company_id,
                KnowledgeBase.status == "active",
            )
        )
        if knowledge_base is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Base de conhecimento ativa nao encontrada para esta empresa",
            )
    changed = payload.model_dump(exclude_unset=True)
    for field, value in changed.items():
        setattr(agent, field, value)
    versioned_fields = {
        "instructions",
        "provider",
        "model",
        "temperature",
        "max_input_tokens",
        "max_output_tokens",
        "memory_enabled",
        "knowledge_base_id",
    }
    if versioned_fields.intersection(changed):
        current = await active_agent_version(database, agent=agent, company_id=context.company_id)
        controls = (
            {
                "autonomy_level": current.autonomy_level,
                "max_steps": current.max_steps,
                "max_runtime_seconds": current.max_runtime_seconds,
                "max_cost_per_run_microunits": current.max_cost_per_run_microunits,
            }
            if current
            else {}
        )
        version_payload = agent_version_payload(agent, **controls)
        version = AgentVersion(
            company_id=context.company_id,
            agent_id=agent.id,
            version=await _next_agent_version(database, agent.id),
            status="draft",
            created_by_user_id=context.user_id,
            checksum=version_checksum(version_payload),
            **version_payload,
        )
        database.add(version)
        await database.flush()
        await _publish_agent_version(
            database, agent=agent, version=version, actor_user_id=context.user_id
        )
    agent.updated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.updated",
        target_type="agent",
        target_id=agent.id,
        details={"fields": sorted(payload.model_fields_set)},
    )
    await database.commit()
    await database.refresh(agent)
    return _agent_response(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_agent(
    agent_id: UUID, principal: CanConfigureAgents, database: DatabaseSession
) -> Response:
    context = get_request_context(principal)
    agent = await _agent(database, agent_id=agent_id, company_id=context.company_id)
    agent.status = "inactive"
    agent.updated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.deactivated",
        target_type="agent",
        target_id=agent.id,
    )
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{agent_id}/tools", response_model=list[AgentToolResponse])
async def list_agent_tools(
    agent_id: UUID, principal: CanViewAgents, database: DatabaseSession
) -> list[AgentToolResponse]:
    context = get_request_context(principal)
    await _agent(database, agent_id=agent_id, company_id=context.company_id)
    tools = (
        await database.scalars(
            select(AgentTool)
            .where(AgentTool.agent_id == agent_id, AgentTool.company_id == context.company_id)
            .order_by(AgentTool.name)
        )
    ).all()
    return [_tool_response(tool) for tool in tools]


@router.put("/{agent_id}/tools", response_model=list[AgentToolResponse])
async def configure_agent_tools(
    agent_id: UUID,
    payload: AgentToolsUpdate,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> list[AgentToolResponse]:
    context = get_request_context(principal)
    await _agent(database, agent_id=agent_id, company_id=context.company_id)
    requested = set(payload.tool_keys)
    unknown = sorted(requested - set(TOOL_CATALOG))
    if unknown:
        raise HTTPException(
            status_code=422, detail=f"Ferramentas desconhecidas: {', '.join(unknown)}."
        )
    existing_rows = (
        await database.scalars(
            select(AgentTool).where(
                AgentTool.agent_id == agent_id, AgentTool.company_id == context.company_id
            )
        )
    ).all()
    existing = {tool.tool_key: tool for tool in existing_rows}
    for tool in existing_rows:
        tool.enabled = tool.tool_key in requested
    for key in requested - set(existing):
        definition = TOOL_CATALOG[key]
        database.add(
            AgentTool(
                company_id=context.company_id,
                agent_id=agent_id,
                tool_key=definition.key,
                name=definition.name,
                description=definition.description,
                input_schema=definition.input_schema,
                required_permission=definition.required_permission,
                risk_level=definition.risk_level,
                is_sensitive=definition.is_sensitive,
                enabled=True,
            )
        )
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.tools.configured",
        target_type="agent",
        target_id=agent_id,
        details={"tool_keys": sorted(requested)},
    )
    await database.commit()
    tools = (
        await database.scalars(
            select(AgentTool)
            .where(
                AgentTool.agent_id == agent_id,
                AgentTool.company_id == context.company_id,
                AgentTool.enabled.is_(True),
            )
            .order_by(AgentTool.name)
        )
    ).all()
    return [_tool_response(tool) for tool in tools]


@router.get("/{agent_id}/versions", response_model=list[AgentVersionResponse])
async def list_agent_versions(
    agent_id: UUID, principal: CanConfigureAgents, database: DatabaseSession
) -> list[AgentVersionResponse]:
    context = get_request_context(principal)
    await _agent(database, agent_id=agent_id, company_id=context.company_id)
    versions = (
        await database.scalars(
            select(AgentVersion)
            .where(
                AgentVersion.agent_id == agent_id,
                AgentVersion.company_id == context.company_id,
            )
            .order_by(AgentVersion.version.desc())
        )
    ).all()
    return [_version_response(version) for version in versions]


@router.post(
    "/{agent_id}/versions",
    response_model=AgentVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_version(
    agent_id: UUID,
    payload: AgentVersionCreate,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentVersionResponse:
    context = get_request_context(principal)
    agent = await _agent(database, agent_id=agent_id, company_id=context.company_id)
    active = await active_agent_version(database, agent=agent, company_id=context.company_id)
    controls = (
        {
            "autonomy_level": active.autonomy_level,
            "max_steps": active.max_steps,
            "max_runtime_seconds": active.max_runtime_seconds,
            "max_cost_per_run_microunits": active.max_cost_per_run_microunits,
        }
        if active
        else {}
    )
    version_payload = agent_version_payload(agent, **controls)
    version_payload.update(payload.model_dump(exclude_unset=True))
    if version_payload.get("knowledge_base_id") is not None:
        knowledge_base = await database.scalar(
            select(KnowledgeBase).where(
                KnowledgeBase.id == version_payload["knowledge_base_id"],
                KnowledgeBase.company_id == context.company_id,
                KnowledgeBase.status == "active",
            )
        )
        if knowledge_base is None:
            raise HTTPException(status_code=422, detail="Base de conhecimento inválida.")
    version = AgentVersion(
        company_id=context.company_id,
        agent_id=agent.id,
        version=await _next_agent_version(database, agent.id),
        status="draft",
        created_by_user_id=context.user_id,
        checksum=version_checksum(version_payload),
        **version_payload,
    )
    database.add(version)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.version.created",
        target_type="agent_version",
        target_id=version.id,
        details={"agent_id": str(agent.id), "version": version.version},
    )
    await database.commit()
    await database.refresh(version)
    return _version_response(version)


@router.post("/{agent_id}/versions/{version_id}/publish", response_model=AgentVersionResponse)
async def publish_agent_version(
    agent_id: UUID,
    version_id: UUID,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentVersionResponse:
    context = get_request_context(principal)
    agent = await _agent(database, agent_id=agent_id, company_id=context.company_id)
    version = await database.scalar(
        select(AgentVersion).where(
            AgentVersion.id == version_id,
            AgentVersion.agent_id == agent.id,
            AgentVersion.company_id == context.company_id,
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Versão do agente não encontrada.")
    if version.status != "draft":
        raise HTTPException(
            status_code=409, detail="Somente versões em rascunho podem ser publicadas."
        )
    await _publish_agent_version(
        database, agent=agent, version=version, actor_user_id=context.user_id
    )
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.version.published",
        target_type="agent_version",
        target_id=version.id,
        details={
            "agent_id": str(agent.id),
            "version": version.version,
            "autonomy_level": version.autonomy_level,
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.version.published",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="internal",
            payload={
                "agent_id": str(agent.id),
                "agent_version_id": str(version.id),
                "version": version.version,
                "autonomy_level": version.autonomy_level,
            },
        ),
    )
    await database.commit()
    await database.refresh(version)
    return _version_response(version)


@router.get("/{agent_id}/budget", response_model=AgentBudgetResponse)
async def get_agent_budget(
    agent_id: UUID, principal: CanConfigureAgents, database: DatabaseSession
) -> AgentBudgetResponse:
    context = get_request_context(principal)
    await _agent(database, agent_id=agent_id, company_id=context.company_id)
    return _budget_response(
        await _budget(database, agent_id=agent_id, company_id=context.company_id)
    )


@router.put("/{agent_id}/budget", response_model=AgentBudgetResponse)
async def update_agent_budget(
    agent_id: UUID,
    payload: AgentBudgetUpdate,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentBudgetResponse:
    context = get_request_context(principal)
    await _agent(database, agent_id=agent_id, company_id=context.company_id)
    budget = await _budget(database, agent_id=agent_id, company_id=context.company_id)
    budget.limit_microunits = payload.limit_microunits
    budget.hard_limit = payload.hard_limit
    budget.updated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.budget.updated",
        target_type="agent_budget",
        target_id=budget.id,
        details={
            "agent_id": str(agent_id),
            "limit_microunits": budget.limit_microunits,
            "hard_limit": budget.hard_limit,
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.budget.updated",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="confidential",
            payload={
                "agent_id": str(agent_id),
                "limit_microunits": budget.limit_microunits,
                "hard_limit": budget.hard_limit,
            },
        ),
    )
    await database.commit()
    await database.refresh(budget)
    return _budget_response(budget)


@router.get("/{agent_id}/runs", response_model=list[AgentRunResponse])
async def list_agent_runs(
    agent_id: UUID,
    principal: CanViewAgents,
    database: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AgentRunResponse]:
    context = get_request_context(principal)
    await _agent(database, agent_id=agent_id, company_id=context.company_id)
    runs = (
        await database.scalars(
            select(AgentRun)
            .where(AgentRun.agent_id == agent_id, AgentRun.company_id == context.company_id)
            .order_by(AgentRun.started_at.desc())
            .limit(limit)
        )
    ).all()
    return [_run_response(run) for run in runs]


@router.get("/{agent_id}/runs/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(
    agent_id: UUID, run_id: UUID, principal: CanViewAgents, database: DatabaseSession
) -> AgentRunResponse:
    context = get_request_context(principal)
    run = await database.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.agent_id == agent_id,
            AgentRun.company_id == context.company_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Execução do agente não encontrada.")
    return _run_response(run)


@router.get("/{agent_id}/data-policy", response_model=AgentDataPolicyResponse)
async def get_agent_data_policy(
    agent_id: UUID, principal: CanConfigureAgents, database: DatabaseSession
) -> AgentDataPolicyResponse:
    context = get_request_context(principal)
    await _agent(database, agent_id=agent_id, company_id=context.company_id)
    return _data_policy_response(
        await _data_policy(database, agent_id=agent_id, company_id=context.company_id)
    )


@router.put("/{agent_id}/data-policy", response_model=AgentDataPolicyResponse)
async def update_agent_data_policy(
    agent_id: UUID,
    payload: AgentDataPolicyUpdate,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentDataPolicyResponse:
    context = get_request_context(principal)
    await _agent(database, agent_id=agent_id, company_id=context.company_id)
    policy = await _data_policy(database, agent_id=agent_id, company_id=context.company_id)
    for field, value in payload.model_dump().items():
        setattr(policy, field, value)
    policy.updated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.data_policy.updated",
        target_type="agent_data_policy",
        target_id=policy.id,
        details={
            "agent_id": str(agent_id),
            "providers": policy.allowed_provider_keys,
            "external_processing_enabled": policy.external_processing_enabled,
            "max_data_classification": policy.max_data_classification,
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.data_policy.updated",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="confidential",
            payload={
                "agent_id": str(agent_id),
                "providers": policy.allowed_provider_keys,
                "external_processing_enabled": policy.external_processing_enabled,
            },
        ),
    )
    await database.commit()
    await database.refresh(policy)
    return _data_policy_response(policy)


@router.get("/{agent_id}/security-events", response_model=list[AgentSecurityEventResponse])
async def list_agent_security_events(
    agent_id: UUID,
    principal: CanConfigureAgents,
    database: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AgentSecurityEventResponse]:
    context = get_request_context(principal)
    await _agent(database, agent_id=agent_id, company_id=context.company_id)
    events = (
        await database.scalars(
            select(AgentSecurityEvent)
            .where(
                AgentSecurityEvent.agent_id == agent_id,
                AgentSecurityEvent.company_id == context.company_id,
            )
            .order_by(AgentSecurityEvent.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [_security_event_response(event) for event in events]


@router.get("/{agent_id}/conversations", response_model=list[AgentConversationResponse])
async def list_conversations(
    agent_id: UUID, principal: CanViewAgents, database: DatabaseSession
) -> list[AgentConversationResponse]:
    context = get_request_context(principal)
    await _agent(database, agent_id=agent_id, company_id=context.company_id)
    conversations = (
        await database.scalars(
            select(AgentConversation)
            .where(
                AgentConversation.agent_id == agent_id,
                AgentConversation.company_id == context.company_id,
            )
            .order_by(AgentConversation.updated_at.desc())
            .limit(100)
        )
    ).all()
    return [_conversation_response(conversation) for conversation in conversations]


@router.post(
    "/{agent_id}/conversations",
    response_model=AgentConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    agent_id: UUID,
    payload: AgentConversationCreate,
    principal: CanExecuteAgents,
    database: DatabaseSession,
) -> AgentConversationResponse:
    context = get_request_context(principal)
    await _agent(database, agent_id=agent_id, company_id=context.company_id)
    conversation = AgentConversation(
        company_id=context.company_id,
        agent_id=agent_id,
        user_id=context.user_id,
        title=(payload.title or "Nova conversa").strip(),
    )
    database.add(conversation)
    await database.commit()
    await database.refresh(conversation)
    return _conversation_response(conversation)


@router.get(
    "/{agent_id}/conversations/{conversation_id}/messages",
    response_model=list[AgentMessageResponse],
)
async def list_messages(
    agent_id: UUID, conversation_id: UUID, principal: CanViewAgents, database: DatabaseSession
) -> list[AgentMessageResponse]:
    context = get_request_context(principal)
    await _conversation(
        database, conversation_id=conversation_id, agent_id=agent_id, company_id=context.company_id
    )
    messages = (
        await database.scalars(
            select(AgentMessage)
            .where(
                AgentMessage.conversation_id == conversation_id,
                AgentMessage.company_id == context.company_id,
            )
            .order_by(AgentMessage.created_at)
        )
    ).all()
    return [_message_response(message) for message in messages]


@router.post("/{agent_id}/chat", response_model=AgentChatResponse)
async def chat_with_agent(
    agent_id: UUID,
    payload: AgentChatRequest,
    principal: CanExecuteAgents,
    database: DatabaseSession,
    settings: RequestSettings,
) -> AgentChatResponse:
    context = get_request_context(principal)
    agent = await _agent(database, agent_id=agent_id, company_id=context.company_id)
    if agent.status != "active":
        raise HTTPException(status_code=409, detail="Este agente está inativo.")
    version = await active_agent_version(database, agent=agent, company_id=context.company_id)
    if version is None:
        raise HTTPException(status_code=409, detail="Este agente não possui versão publicada.")
    data_policy = await _data_policy(database, agent_id=agent.id, company_id=context.company_id)
    try:
        assert_provider_data_policy(
            data_policy,
            provider=version.provider,
            includes_knowledge=version.knowledge_base_id is not None,
        )
    except AgentDataPolicyViolation as exc:
        fingerprint = agent_request_fingerprint(
            company_id=context.company_id, agent_id=agent.id, message=version.provider
        )
        database.add(
            AgentSecurityEvent(
                company_id=context.company_id,
                agent_id=agent.id,
                category="data_egress",
                source="provider",
                severity="high",
                action="blocked",
                content_fingerprint=fingerprint,
                indicators=["provider_policy_denied"],
            )
        )
        await database.commit()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    injection = scan_prompt_injection(payload.message)
    if injection.detected:
        database.add(
            AgentSecurityEvent(
                company_id=context.company_id,
                agent_id=agent.id,
                category="prompt_injection",
                source="user",
                severity="high",
                action="blocked",
                content_fingerprint=injection.fingerprint,
                indicators=list(injection.indicators),
            )
        )
        record_authorization_audit(
            database,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            action="agent.prompt_injection.blocked",
            target_type="agent",
            target_id=agent.id,
            details={"indicators": list(injection.indicators)},
        )
        await database.commit()
        raise HTTPException(
            status_code=422,
            detail="A solicitação foi bloqueada pela política de segurança do agente.",
        )
    projected_tokens = max(1, len(payload.message) // 4) + agent.max_output_tokens
    await enforce_limit(
        database,
        company_id=context.company_id,
        metric=UsageMetric.TOKENS,
        increment=projected_tokens,
        enforcement_enabled=settings.billing_enforcement_enabled,
    )
    try:
        _, budget_reservation = await reserve_agent_budget(
            database,
            company_id=context.company_id,
            agent_id=agent.id,
            requested_microunits=version.max_cost_per_run_microunits,
        )
    except AgentBudgetExceededError as exc:
        await database.rollback()
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    if payload.conversation_id:
        conversation = await _conversation(
            database,
            conversation_id=payload.conversation_id,
            agent_id=agent.id,
            company_id=context.company_id,
        )
    else:
        conversation = AgentConversation(
            company_id=context.company_id,
            agent_id=agent.id,
            user_id=context.user_id,
            title=payload.message[:80],
        )
        database.add(conversation)
        await database.flush()
    user_message = AgentMessage(
        company_id=context.company_id,
        conversation_id=conversation.id,
        agent_id=agent.id,
        user_id=context.user_id,
        role="user",
        content=payload.message,
    )
    database.add(user_message)
    await database.flush()
    agent_run = AgentRun(
        company_id=context.company_id,
        agent_id=agent.id,
        agent_version_id=version.id,
        conversation_id=conversation.id,
        requested_by_user_id=context.user_id,
        execution_mode=payload.execution_mode,
        status="running",
        request_fingerprint=agent_request_fingerprint(
            company_id=context.company_id, agent_id=agent.id, message=payload.message
        ),
        max_steps=version.max_steps,
        max_runtime_seconds=version.max_runtime_seconds,
    )
    database.add(agent_run)
    await database.flush()
    await database.commit()
    history = list(
        await database.scalars(
            select(AgentMessage)
            .where(AgentMessage.conversation_id == conversation.id)
            .order_by(AgentMessage.created_at.desc())
            .limit(20)
        )
    )
    history.reverse()
    tools = (
        await database.scalars(
            select(AgentTool).where(
                AgentTool.agent_id == agent.id,
                AgentTool.company_id == context.company_id,
                AgentTool.enabled.is_(True),
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
        if version.autonomy_level >= 2
    ]
    sources = (
        await search_knowledge(
            database,
            settings=settings,
            company_id=context.company_id,
            base_id=agent.knowledge_base_id,
            query=payload.message,
        )
        if agent.knowledge_base_id
        else []
    )
    safe_sources: list[dict[str, Any]] = []
    for source in sources:
        assessment = scan_prompt_injection(str(source["content"]))
        if assessment.detected:
            database.add(
                AgentSecurityEvent(
                    company_id=context.company_id,
                    agent_id=agent.id,
                    agent_run_id=agent_run.id,
                    category="prompt_injection",
                    source="knowledge",
                    severity="critical",
                    action="blocked",
                    content_fingerprint=assessment.fingerprint,
                    indicators=list(assessment.indicators),
                )
            )
            continue
        protected_content, redacted = protect_provider_text(
            data_policy, provider=version.provider, text=str(source["content"])
        )
        safe_source = dict(source)
        safe_source["content"] = protected_content
        safe_sources.append(safe_source)
        if redacted:
            database.add(
                AgentSecurityEvent(
                    company_id=context.company_id,
                    agent_id=agent.id,
                    agent_run_id=agent_run.id,
                    category="sensitive_data",
                    source="knowledge",
                    severity="medium",
                    action="redacted",
                    content_fingerprint=assessment.fingerprint,
                    indicators=["sensitive_data_redacted"],
                )
            )
    sources = safe_sources
    knowledge_context = "\n\n".join(
        f"[Fonte {item['document_name']} trecho {item['chunk_index']}] {item['content']}"
        for item in sources
    )
    provider_messages = (
        [
            ModelMessage(
                role="system",
                content=protect_provider_text(
                    data_policy, provider=version.provider, text=version.instructions
                )[0],
            )
        ]
        + (
            [
                ModelMessage(
                    role="system",
                    content="Use apenas estas fontes internas autorizadas:\n" + knowledge_context,
                )
            ]
            if knowledge_context
            else []
        )
        + [
            ModelMessage(
                role=cast(
                    Literal["system", "user", "assistant", "tool"],
                    message.role,
                ),
                content=protect_provider_text(
                    data_policy, provider=version.provider, text=message.content
                )[0],
            )
            for message in history
        ]
    )
    started = perf_counter()
    try:
        provider = create_language_model_provider(version.provider, settings)
        async with asyncio.timeout(version.max_runtime_seconds):
            result = await provider.generate(
                messages=provider_messages,
                tools=provider_tools,
                model=version.model,
                temperature=version.temperature,
                max_output_tokens=version.max_output_tokens,
            )
            usage = await provider.calculate_usage(result)
    except (LanguageModelProviderError, TimeoutError) as exc:
        agent_run.status = "timed_out" if isinstance(exc, TimeoutError) else "failed"
        agent_run.error_code = (
            "provider_timeout" if isinstance(exc, TimeoutError) else "provider_error"
        )
        agent_run.finished_at = utc_now()
        agent_run.duration_ms = max(0, round((perf_counter() - started) * 1_000))
        await settle_agent_budget(
            database,
            company_id=context.company_id,
            agent_id=agent.id,
            reserved_microunits=budget_reservation,
            consumed_microunits=0,
        )
        await database.commit()
        detail = (
            "O provedor de IA excedeu o tempo permitido."
            if isinstance(exc, TimeoutError)
            else str(exc)
        )
        raise HTTPException(
            status_code=504 if isinstance(exc, TimeoutError) else 502, detail=detail
        ) from exc
    agent_run.planned_tool_keys = [call.key for call in result.tool_calls]
    agent_run.total_tokens = usage.total_tokens
    agent_run.cost_microunits = usage.cost_microunits
    await settle_agent_budget(
        database,
        company_id=context.company_id,
        agent_id=agent.id,
        reserved_microunits=budget_reservation,
        consumed_microunits=usage.cost_microunits,
    )
    await database.commit()
    tool_by_key = {tool.tool_key: tool for tool in tools}
    created_runs: list[AgentToolRun] = []
    result_messages: list[str] = []
    result_status = "completed"
    tool_keys: list[str] = []
    completed_tool_keys: list[str] = []
    denied_tool_keys: list[str] = []
    for call_index, call in enumerate(result.tool_calls):
        tool_keys.append(call.key)
        limit_decision = evaluate_run_limits(
            tool_call_index=call_index,
            max_steps=version.max_steps,
            elapsed_seconds=perf_counter() - started,
            max_runtime_seconds=version.max_runtime_seconds,
        )
        if not limit_decision.allowed:
            denied_tool_keys.append(call.key)
            agent_run.error_code = limit_decision.error_code
            result_status = "failed"
            result_messages.append(f"Ferramenta bloqueada: {limit_decision.reason}")
            continue
        tool = tool_by_key.get(call.key)
        if tool is None:
            denied_tool_keys.append(call.key)
            result_status = "failed"
            result_messages.append(f"Ferramenta bloqueada: {call.key} não está autorizada.")
            continue
        try:
            assert_tool_access(tool, principal.permissions)
            validate_tool_arguments(tool.input_schema, call.arguments)
        except (ToolAccessError, ToolArgumentsError) as exc:
            denied_tool_keys.append(call.key)
            result_status = "failed"
            result_messages.append(f"Ferramenta bloqueada: {exc}")
            continue
        autonomy = evaluate_tool_autonomy(
            autonomy_level=version.autonomy_level, risk_level=tool.risk_level
        )
        if not autonomy.allowed:
            denied_tool_keys.append(call.key)
            result_status = "failed"
            result_messages.append(f"Ferramenta bloqueada: {autonomy.reason}")
            continue
        if payload.execution_mode != "live":
            completed_tool_keys.append(call.key)
            result_status = "simulated"
            result_messages.append(
                f"Simulação segura: a ferramenta {tool.name} seria executada, sem alterar dados."
            )
            continue
        run = AgentToolRun(
            company_id=context.company_id,
            agent_id=agent.id,
            agent_version_id=version.id,
            agent_run_id=agent_run.id,
            conversation_id=conversation.id,
            tool_id=tool.id,
            requested_by_user_id=context.user_id,
            state="awaiting_confirmation" if autonomy.requires_approval else "executing",
            arguments=as_summary_object(call.arguments),
            requires_confirmation=autonomy.requires_approval,
            started_at=None if autonomy.requires_approval else utc_now(),
        )
        database.add(run)
        await database.flush()
        created_runs.append(run)
        if autonomy.requires_approval:
            await create_approval_request(
                database,
                company_id=context.company_id,
                requested_by_user_id=context.user_id,
                source_type="agent",
                title=f"Autorizar ação do agente {agent.name}",
                description=f"A ferramenta {tool.name} exige confirmação humana antes da execução.",
                context={
                    "agent_id": str(agent.id),
                    "agent_name": agent.name,
                    "tool_key": tool.tool_key,
                    "tool_name": tool.name,
                    "arguments": run.arguments,
                },
                agent_tool_run_id=run.id,
                reminder_minutes=settings.notification_reminder_minutes,
            )
            result_status = "awaiting_confirmation"
            result_messages.append(f"A ação {tool.name} aguarda sua confirmação.")
            continue
        try:
            tool_result = await execute_builtin_tool(
                tool_key=tool.tool_key,
                arguments=call.arguments,
                company_id=context.company_id,
                database=database,
                settings=settings,
            )
            run.result_summary = as_summary_object(tool_result)
            run.state = "completed"
            completed_tool_keys.append(tool.tool_key)
            result_messages.append(f"Ferramenta {tool.name} executada com sucesso.")
        except (ToolArgumentsError, ToolExecutionError) as exc:
            run.state = "failed"
            run.error_summary = str(exc)
            result_status = "failed"
            result_messages.append(f"A ferramenta {tool.name} falhou: {exc}")
        run.finished_at = utc_now()
    duration_ms = max(0, round((perf_counter() - started) * 1_000))
    source_note = (
        "\n\nFontes internas: "
        + ", ".join(f"{x['document_name']} (trecho {x['chunk_index']})" for x in sources)
        if sources
        else ""
    )
    assistant_message = AgentMessage(
        company_id=context.company_id,
        conversation_id=conversation.id,
        agent_id=agent.id,
        role="assistant",
        content=("\n".join(result_messages) or result.content or "O agente concluiu sem conteúdo.")
        + source_note,
        tool_call={
            "calls": [{"tool_key": call.key, "state": result_status} for call in result.tool_calls],
            "sources": sources,
        },
        provider=version.provider,
        model=version.model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
        cost_microunits=usage.cost_microunits,
        duration_ms=duration_ms,
    )
    database.add(assistant_message)
    await database.flush()
    for run in created_runs:
        run.message_id = assistant_message.id
    conversation.updated_at = utc_now()
    database.add(
        AgentUsageRecord(
            company_id=context.company_id,
            user_id=context.user_id,
            agent_id=agent.id,
            agent_version_id=version.id,
            agent_run_id=agent_run.id,
            conversation_id=conversation.id,
            provider=version.provider,
            model=version.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            cost_microunits=usage.cost_microunits,
            tool_key=",".join(tool_keys)[:120] or None,
            duration_ms=duration_ms,
            result_status=result_status,
        )
    )
    await record_usage(
        database,
        company_id=context.company_id,
        metric=UsageMetric.TOKENS,
        quantity=usage.total_tokens,
        metadata={
            "agent_id": str(agent.id),
            "conversation_id": str(conversation.id),
            "provider": agent.provider,
        },
        idempotency_key=f"agent-message:{assistant_message.id}",
    )
    agent_run.completed_tool_keys = completed_tool_keys
    agent_run.denied_tool_keys = denied_tool_keys
    agent_run.step_count = min(len(result.tool_calls), version.max_steps)
    agent_run.duration_ms = duration_ms
    agent_run.finished_at = utc_now()
    if payload.execution_mode != "live":
        agent_run.status = "simulated"
    elif any(run.state == "awaiting_confirmation" for run in created_runs):
        agent_run.status = "awaiting_approval"
    elif result_status == "failed":
        agent_run.status = "failed"
    else:
        agent_run.status = "completed"
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action=f"agent.run.{agent_run.status}",
        target_type="agent_run",
        target_id=agent_run.id,
        details={
            "agent_id": str(agent.id),
            "agent_version_id": str(version.id),
            "execution_mode": agent_run.execution_mode,
            "step_count": agent_run.step_count,
            "error_code": agent_run.error_code,
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=f"agent.run.{agent_run.status}",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="confidential",
            payload={
                "agent_id": str(agent.id),
                "agent_version_id": str(version.id),
                "agent_run_id": str(agent_run.id),
                "status": agent_run.status,
                "execution_mode": agent_run.execution_mode,
                "step_count": agent_run.step_count,
                "cost_microunits": agent_run.cost_microunits,
            },
        ),
    )
    await database.commit()
    await database.refresh(conversation)
    await database.refresh(user_message)
    await database.refresh(assistant_message)
    await database.refresh(agent_run)
    for run in created_runs:
        await database.refresh(run)
    pending = [
        await _tool_run_response(database, run)
        for run in created_runs
        if run.state == "awaiting_confirmation"
    ]
    return AgentChatResponse(
        conversation=_conversation_response(conversation),
        user_message=_message_response(user_message),
        assistant_message=_message_response(assistant_message),
        pending_actions=pending,
        run=_run_response(agent_run),
    )
