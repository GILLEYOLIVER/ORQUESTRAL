from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.agents.approval_policy import evaluate_agent_approval_policy
from app.modules.agents.approval_policy_models import AgentApprovalPolicyVersion
from app.modules.agents.approval_policy_schemas import (
    AgentApprovalPolicyCreate,
    AgentApprovalPolicyEvaluationRequest,
    AgentApprovalPolicyEvaluationResponse,
    AgentApprovalPolicyResponse,
)
from app.modules.agents.models import Agent
from app.modules.agents.tools import TOOL_CATALOG
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.users.models import CompanyUser

router = APIRouter()
CanConfigureAgents = Annotated[Principal, Depends(require_permission("agents.configure"))]


async def _tenant_agent(database: DatabaseSession, *, company_id: UUID, agent_id: UUID) -> Agent:
    agent = await database.scalar(
        select(Agent).where(Agent.id == agent_id, Agent.company_id == company_id)
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Agente não encontrado.")
    return agent


def _response(policy: AgentApprovalPolicyVersion) -> AgentApprovalPolicyResponse:
    return AgentApprovalPolicyResponse.model_validate(policy, from_attributes=True)


@router.get(
    "/{agent_id}/approval-policies",
    response_model=list[AgentApprovalPolicyResponse],
)
async def list_agent_approval_policies(
    agent_id: UUID,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> list[AgentApprovalPolicyResponse]:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    policies = (
        await database.scalars(
            select(AgentApprovalPolicyVersion)
            .where(
                AgentApprovalPolicyVersion.company_id == context.company_id,
                AgentApprovalPolicyVersion.agent_id == agent_id,
            )
            .order_by(
                AgentApprovalPolicyVersion.policy_key,
                AgentApprovalPolicyVersion.version.desc(),
            )
        )
    ).all()
    return [_response(policy) for policy in policies]


@router.post(
    "/{agent_id}/approval-policies",
    response_model=AgentApprovalPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_approval_policy(
    agent_id: UUID,
    payload: AgentApprovalPolicyCreate,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentApprovalPolicyResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    if payload.tool_key is not None and payload.tool_key not in TOOL_CATALOG:
        raise HTTPException(status_code=422, detail="Ferramenta desconhecida.")
    if payload.assigned_user_id is not None:
        member = await database.scalar(
            select(CompanyUser).where(
                CompanyUser.company_id == context.company_id,
                CompanyUser.user_id == payload.assigned_user_id,
                CompanyUser.status == "active",
            )
        )
        if member is None:
            raise HTTPException(status_code=422, detail="Aprovador não pertence à empresa.")
    current_version = await database.scalar(
        select(func.max(AgentApprovalPolicyVersion.version)).where(
            AgentApprovalPolicyVersion.company_id == context.company_id,
            AgentApprovalPolicyVersion.agent_id == agent_id,
            AgentApprovalPolicyVersion.policy_key == payload.policy_key,
        )
    )
    policy = AgentApprovalPolicyVersion(
        company_id=context.company_id,
        agent_id=agent_id,
        version=(current_version or 0) + 1,
        status="draft",
        created_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    database.add(policy)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.approval_policy.created",
        target_type="agent_approval_policy",
        target_id=policy.id,
        details={
            "agent_id": str(agent_id),
            "policy_key": policy.policy_key,
            "version": policy.version,
            "effect": policy.effect,
        },
    )
    await database.commit()
    await database.refresh(policy)
    return _response(policy)


@router.post(
    "/{agent_id}/approval-policies/{policy_id}/publish",
    response_model=AgentApprovalPolicyResponse,
)
async def publish_agent_approval_policy(
    agent_id: UUID,
    policy_id: UUID,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentApprovalPolicyResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    policy = await database.scalar(
        select(AgentApprovalPolicyVersion)
        .where(
            AgentApprovalPolicyVersion.id == policy_id,
            AgentApprovalPolicyVersion.company_id == context.company_id,
            AgentApprovalPolicyVersion.agent_id == agent_id,
        )
        .with_for_update()
    )
    if policy is None:
        raise HTTPException(status_code=404, detail="Política não encontrada.")
    if policy.status != "draft":
        raise HTTPException(status_code=409, detail="Somente rascunhos podem ser publicados.")
    published = (
        await database.scalars(
            select(AgentApprovalPolicyVersion)
            .where(
                AgentApprovalPolicyVersion.company_id == context.company_id,
                AgentApprovalPolicyVersion.agent_id == agent_id,
                AgentApprovalPolicyVersion.policy_key == policy.policy_key,
                AgentApprovalPolicyVersion.status == "published",
            )
            .with_for_update()
        )
    ).all()
    for previous in published:
        previous.status = "retired"
    policy.status = "published"
    policy.published_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.approval_policy.published",
        target_type="agent_approval_policy",
        target_id=policy.id,
        details={
            "agent_id": str(agent_id),
            "policy_key": policy.policy_key,
            "version": policy.version,
            "effect": policy.effect,
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.approval_policy.published",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="confidential",
            payload={
                "agent_id": str(agent_id),
                "policy_version_id": str(policy.id),
                "policy_key": policy.policy_key,
                "version": policy.version,
                "effect": policy.effect,
            },
        ),
    )
    await database.commit()
    await database.refresh(policy)
    return _response(policy)


@router.post(
    "/{agent_id}/approval-policies/evaluate",
    response_model=AgentApprovalPolicyEvaluationResponse,
)
async def evaluate_agent_approval_policy_endpoint(
    agent_id: UUID,
    payload: AgentApprovalPolicyEvaluationRequest,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentApprovalPolicyEvaluationResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    if payload.tool_key not in TOOL_CATALOG:
        raise HTTPException(status_code=422, detail="Ferramenta desconhecida.")
    decision = await evaluate_agent_approval_policy(
        database,
        company_id=context.company_id,
        agent_id=agent_id,
        tool_key=payload.tool_key,
        arguments=payload.arguments,
    )
    return AgentApprovalPolicyEvaluationResponse(
        allowed=decision.allowed,
        requires_approval=decision.requires_approval,
        policy_version_id=decision.policy_version_id,
        policy_key=decision.policy_key,
        reason=decision.reason,
        approval_ttl_minutes=decision.approval_ttl_minutes,
        assigned_user_id=decision.assigned_user_id,
    )
