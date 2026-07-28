from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.agents.models import Agent, AgentVersion
from app.modules.support.agent_handoff_models import SupportAgentAssistRun, SupportHumanHandoff
from app.modules.support.agent_handoff_schemas import (
    SupportAgentAssistCreate,
    SupportAgentAssistResponse,
    SupportHumanHandoffCreate,
    SupportHumanHandoffDecision,
    SupportHumanHandoffResponse,
)
from app.modules.support.agent_handoff_service import authorized_context, decide_support_action
from app.modules.support.models import SupportTicket, SupportTicketEvent
from app.modules.users.models import CompanyUser

router = APIRouter(prefix="/support/agent-assist", tags=["support-agent-assist"])
CanView = Annotated[Principal, Depends(require_permission("support.tickets.view"))]
CanUpdate = Annotated[Principal, Depends(require_permission("support.tickets.update"))]
CanExecute = Annotated[Principal, Depends(require_permission("agents.execute"))]


async def _ticket(database: DatabaseSession, company_id: UUID, ticket_id: UUID) -> SupportTicket:
    ticket: SupportTicket | None = await database.scalar(
        select(SupportTicket).where(
            SupportTicket.company_id == company_id,
            SupportTicket.id == ticket_id,
        )
    )
    if not ticket:
        raise HTTPException(404, "Chamado não encontrado.")
    return ticket


@router.get("/tickets/{ticket_id}/runs", response_model=list[SupportAgentAssistResponse])
async def list_assist_runs(
    ticket_id: UUID, principal: CanView, database: DatabaseSession
) -> list[SupportAgentAssistRun]:
    context = get_request_context(principal)
    await _ticket(database, context.company_id, ticket_id)
    return list(
        await database.scalars(
            select(SupportAgentAssistRun)
            .where(
                SupportAgentAssistRun.company_id == context.company_id,
                SupportAgentAssistRun.ticket_id == ticket_id,
            )
            .order_by(SupportAgentAssistRun.created_at.desc())
        )
    )


@router.post(
    "/tickets/{ticket_id}/runs",
    response_model=SupportAgentAssistResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_assist_run(
    ticket_id: UUID,
    payload: SupportAgentAssistCreate,
    principal: CanExecute,
    database: DatabaseSession,
) -> SupportAgentAssistRun:
    context = get_request_context(principal)
    ticket = await _ticket(database, context.company_id, ticket_id)
    agent = await database.scalar(
        select(Agent).where(
            Agent.company_id == context.company_id,
            Agent.id == payload.agent_id,
            Agent.status == "active",
        )
    )
    if not agent or not agent.active_version_id:
        raise HTTPException(409, "Selecione um agente ativo e publicado.")
    version = await database.scalar(
        select(AgentVersion).where(
            AgentVersion.company_id == context.company_id,
            AgentVersion.agent_id == agent.id,
            AgentVersion.id == agent.active_version_id,
            AgentVersion.status == "published",
        )
    )
    if not version:
        raise HTTPException(409, "A versão ativa do agente não está publicada.")
    refs, interaction_count, citation_count = await authorized_context(
        database, company_id=context.company_id, ticket=ticket
    )
    decision = decide_support_action(
        priority=ticket.priority,
        breached=ticket.breached_at is not None,
        interaction_count=interaction_count,
        citation_count=citation_count,
    )
    run = SupportAgentAssistRun(
        company_id=context.company_id,
        ticket_id=ticket.id,
        agent_id=agent.id,
        agent_version_id=version.id,
        requested_by_user_id=context.user_id,
        recommendation=decision.recommendation,
        reason_code=decision.reason_code,
        context_refs=refs,
        citation_count=citation_count,
    )
    database.add(run)
    database.add(
        SupportTicketEvent(
            company_id=context.company_id,
            ticket_id=ticket.id,
            actor_user_id=context.user_id,
            event_type="agent_assist_proposed",
            description="Agente propôs a próxima ação.",
            details={
                "recommendation": decision.recommendation,
                "reason_code": decision.reason_code,
                "context_reference_count": len(refs),
                "citation_count": citation_count,
            },
        )
    )
    await database.commit()
    await database.refresh(run)
    return run


@router.post(
    "/runs/{run_id}/handoffs",
    response_model=SupportHumanHandoffResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_human_handoff(
    run_id: UUID,
    payload: SupportHumanHandoffCreate,
    principal: CanUpdate,
    database: DatabaseSession,
) -> SupportHumanHandoff:
    context = get_request_context(principal)
    run = await database.scalar(
        select(SupportAgentAssistRun).where(
            SupportAgentAssistRun.company_id == context.company_id,
            SupportAgentAssistRun.id == run_id,
            SupportAgentAssistRun.status == "proposed",
        )
    )
    target = await database.scalar(
        select(CompanyUser.id).where(
            CompanyUser.company_id == context.company_id,
            CompanyUser.user_id == payload.target_user_id,
        )
    )
    if not run or not target:
        raise HTTPException(422, "Execução ou destinatário inválido.")
    handoff = SupportHumanHandoff(
        company_id=context.company_id,
        assist_run_id=run.id,
        ticket_id=run.ticket_id,
        target_user_id=payload.target_user_id,
        requested_by_user_id=context.user_id,
        reason_code=payload.reason_code,
    )
    run.status = "handoff_requested"
    database.add(handoff)
    await database.commit()
    await database.refresh(handoff)
    return handoff


@router.post(
    "/handoffs/{handoff_id}/decision",
    response_model=SupportHumanHandoffResponse,
)
async def decide_human_handoff(
    handoff_id: UUID,
    payload: SupportHumanHandoffDecision,
    principal: CanUpdate,
    database: DatabaseSession,
) -> SupportHumanHandoff:
    context = get_request_context(principal)
    handoff = await database.scalar(
        select(SupportHumanHandoff).where(
            SupportHumanHandoff.company_id == context.company_id,
            SupportHumanHandoff.id == handoff_id,
            SupportHumanHandoff.status == "requested",
        )
    )
    if not handoff:
        raise HTTPException(404, "Transferência pendente não encontrada.")
    run = await database.scalar(
        select(SupportAgentAssistRun).where(
            SupportAgentAssistRun.company_id == context.company_id,
            SupportAgentAssistRun.id == handoff.assist_run_id,
        )
    )
    ticket = await _ticket(database, context.company_id, handoff.ticket_id)
    now = datetime.now(UTC)
    handoff.status = payload.decision
    handoff.decided_by_user_id = context.user_id
    handoff.decided_at = now
    if payload.decision == "accepted":
        ticket.assignee_user_id = handoff.target_user_id
        ticket.status = "in_progress"
        if run:
            run.status = "completed"
            run.completed_at = now
    elif run:
        run.status = "cancelled"
        run.completed_at = now
    database.add(
        SupportTicketEvent(
            company_id=context.company_id,
            ticket_id=ticket.id,
            actor_user_id=context.user_id,
            event_type="human_handoff_decided",
            description="Transferência humana decidida.",
            details={"decision": payload.decision, "reason_code": handoff.reason_code},
        )
    )
    await database.commit()
    await database.refresh(handoff)
    return handoff

