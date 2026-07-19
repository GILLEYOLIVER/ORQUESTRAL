from __future__ import annotations

from time import perf_counter
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select

from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.agents.models import (
    Agent,
    AgentConversation,
    AgentMessage,
    AgentTool,
    AgentToolRun,
    AgentUsageRecord,
)
from app.modules.agents.providers.base import (
    LanguageModelProviderError,
    ModelMessage,
    ToolDefinition,
)
from app.modules.agents.providers.factory import create_language_model_provider
from app.modules.agents.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    AgentConversationCreate,
    AgentConversationResponse,
    AgentCreate,
    AgentMessageResponse,
    AgentProviderStatusResponse,
    AgentResponse,
    AgentToolCatalogResponse,
    AgentToolDecision,
    AgentToolResponse,
    AgentToolRunResponse,
    AgentToolsUpdate,
    AgentUpdate,
    AgentUsageResponse,
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
from app.modules.knowledge.models import KnowledgeBase
from app.modules.knowledge.processing import search_knowledge
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
    run = await database.scalar(
        select(AgentToolRun).where(
            AgentToolRun.id == run_id, AgentToolRun.company_id == context.company_id
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Ação não encontrada nesta empresa.")
    if run.state != "awaiting_confirmation":
        raise HTTPException(status_code=409, detail="Esta ação já recebeu uma decisão.")
    tool = await database.scalar(
        select(AgentTool).where(
            AgentTool.id == run.tool_id, AgentTool.company_id == context.company_id
        )
    )
    if tool is None:
        raise HTTPException(status_code=404, detail="Ferramenta da ação não encontrada.")
    now = utc_now()
    if payload.decision == "rejected":
        run.state = "rejected"
        run.rejected_by_user_id = context.user_id
        run.rejected_at = now
        run.finished_at = now
    else:
        run.approved_by_user_id = context.user_id
        run.approved_at = now
        try:
            assert_tool_access(tool, principal.permissions)
            validate_tool_arguments(tool.input_schema, run.arguments)
            run.state = "executing"
            run.started_at = now
            result = await execute_builtin_tool(
                tool_key=tool.tool_key,
                arguments=run.arguments,
                company_id=context.company_id,
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
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action=f"agent.tool.{run.state}",
        target_type="agent_tool_run",
        target_id=run.id,
        details={"tool_key": tool.tool_key, "decision": payload.decision},
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
async def list_agents(principal: CanViewAgents, database: DatabaseSession) -> list[AgentResponse]:
    context = get_request_context(principal)
    agents = (
        await database.scalars(
            select(Agent)
            .where(Agent.company_id == context.company_id)
            .order_by(Agent.created_at.desc())
        )
    ).all()
    return [_agent_response(agent) for agent in agents]


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate, principal: CanCreateAgents, database: DatabaseSession
) -> AgentResponse:
    context = get_request_context(principal)
    agent = Agent(
        company_id=context.company_id, created_by_user_id=context.user_id, **payload.model_dump()
    )
    database.add(agent)
    await database.flush()
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
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
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
    knowledge_context = "\n\n".join(
        f"[Fonte {item['document_name']} trecho {item['chunk_index']}] {item['content']}"
        for item in sources
    )
    provider_messages = (
        [ModelMessage(role="system", content=agent.instructions)]
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
                content=message.content,
            )
            for message in history
        ]
    )
    started = perf_counter()
    try:
        provider = create_language_model_provider(agent.provider, settings)
        result = await provider.generate(
            messages=provider_messages,
            tools=provider_tools,
            model=agent.model,
            temperature=agent.temperature,
            max_output_tokens=agent.max_output_tokens,
        )
        usage = await provider.calculate_usage(result)
    except LanguageModelProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    tool_by_key = {tool.tool_key: tool for tool in tools}
    created_runs: list[AgentToolRun] = []
    result_messages: list[str] = []
    result_status = "completed"
    tool_keys: list[str] = []
    for call in result.tool_calls:
        tool_keys.append(call.key)
        tool = tool_by_key.get(call.key)
        if tool is None:
            result_status = "failed"
            result_messages.append(f"Ferramenta bloqueada: {call.key} não está autorizada.")
            continue
        try:
            assert_tool_access(tool, principal.permissions)
            validate_tool_arguments(tool.input_schema, call.arguments)
        except (ToolAccessError, ToolArgumentsError) as exc:
            result_status = "failed"
            result_messages.append(f"Ferramenta bloqueada: {exc}")
            continue
        run = AgentToolRun(
            company_id=context.company_id,
            agent_id=agent.id,
            conversation_id=conversation.id,
            tool_id=tool.id,
            requested_by_user_id=context.user_id,
            state="awaiting_confirmation" if tool.is_sensitive else "executing",
            arguments=as_summary_object(call.arguments),
            requires_confirmation=tool.is_sensitive,
            started_at=None if tool.is_sensitive else utc_now(),
        )
        database.add(run)
        await database.flush()
        created_runs.append(run)
        if tool.is_sensitive:
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
        provider=agent.provider,
        model=agent.model,
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
            conversation_id=conversation.id,
            provider=agent.provider,
            model=agent.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            cost_microunits=usage.cost_microunits,
            tool_key=",".join(tool_keys)[:120] or None,
            duration_ms=duration_ms,
            result_status=result_status,
        )
    )
    await database.commit()
    await database.refresh(conversation)
    await database.refresh(user_message)
    await database.refresh(assistant_message)
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
    )
