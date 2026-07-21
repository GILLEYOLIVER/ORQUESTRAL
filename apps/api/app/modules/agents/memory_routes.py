from __future__ import annotations

from datetime import timedelta
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select

from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.agents.memory_models import (
    AgentMemoryConsentRevocation,
    AgentMemoryEntry,
    AgentMemoryPolicy,
    AgentMemoryScopePolicy,
)
from app.modules.agents.memory_schemas import (
    AgentMemoryConsentRevocationResponse,
    AgentMemoryConsentRevoke,
    AgentMemoryCreate,
    AgentMemoryPolicyResponse,
    AgentMemoryPolicyUpdate,
    AgentMemoryPurgeRequest,
    AgentMemoryPurgeResponse,
    AgentMemoryResponse,
    AgentMemoryScopePolicyInput,
    MemoryClassification,
    MemoryScope,
    MemorySource,
)
from app.modules.agents.memory_service import (
    memory_consent_fingerprint,
    memory_content_fingerprint,
    memory_is_expired,
    memory_policy_values,
)
from app.modules.agents.models import Agent
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.plugins.crypto import CredentialVault
from app.modules.users.models import CompanyUser

router = APIRouter()
CanConfigureAgentMemory = Annotated[Principal, Depends(require_permission("agents.configure"))]


async def _tenant_agent(database: DatabaseSession, *, company_id: UUID, agent_id: UUID) -> Agent:
    agent = await database.scalar(
        select(Agent).where(Agent.id == agent_id, Agent.company_id == company_id)
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Agente não encontrado.")
    return agent


async def _memory_policy(
    database: DatabaseSession, *, company_id: UUID, agent_id: UUID
) -> AgentMemoryPolicy | None:
    policy: AgentMemoryPolicy | None = await database.scalar(
        select(AgentMemoryPolicy).where(
            AgentMemoryPolicy.company_id == company_id,
            AgentMemoryPolicy.agent_id == agent_id,
        )
    )
    return policy


async def _memory_scope_policies(
    database: DatabaseSession, *, company_id: UUID, agent_id: UUID
) -> list[AgentMemoryScopePolicy]:
    return list(
        await database.scalars(
            select(AgentMemoryScopePolicy).where(
                AgentMemoryScopePolicy.company_id == company_id,
                AgentMemoryScopePolicy.agent_id == agent_id,
            )
        )
    )


async def _active_company_user(
    database: DatabaseSession, *, company_id: UUID, user_id: UUID
) -> CompanyUser:
    membership = await database.scalar(
        select(CompanyUser).where(
            CompanyUser.company_id == company_id,
            CompanyUser.user_id == user_id,
            CompanyUser.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=422, detail="O titular não pertence à empresa ativa.")
    return membership


def _policy_response(
    agent_id: UUID,
    policy: AgentMemoryPolicy | None,
    scope_policies: list[AgentMemoryScopePolicy],
) -> AgentMemoryPolicyResponse:
    values = memory_policy_values(policy, scope_policies)
    return AgentMemoryPolicyResponse(
        id=policy.id if policy else None,
        agent_id=agent_id,
        default_retention_days=cast(int, values["default_retention_days"]),
        max_retention_days=cast(int, values["max_retention_days"]),
        allowed_scopes=cast(list[MemoryScope], values["allowed_scopes"]),
        allowed_classifications=cast(list[MemoryClassification], values["allowed_classifications"]),
        require_consent_for_user_scope=cast(bool, values["require_consent_for_user_scope"]),
        retrieval_enabled=cast(bool, values["retrieval_enabled"]),
        max_retrieval_entries=cast(int, values["max_retrieval_entries"]),
        max_context_tokens=cast(int, values["max_context_tokens"]),
        scope_policies=[
            AgentMemoryScopePolicyInput.model_validate(item)
            for item in cast(list[dict[str, object]], values["scope_policies"])
        ],
        updated_at=policy.updated_at if policy else None,
    )


def _memory_response(memory: AgentMemoryEntry) -> AgentMemoryResponse:
    return AgentMemoryResponse(
        id=memory.id,
        agent_id=memory.agent_id,
        scope=cast(MemoryScope, memory.scope),
        classification=cast(MemoryClassification, memory.classification),
        source_type=cast(MemorySource, memory.source_type),
        source_id=memory.source_id,
        subject_user_id=memory.subject_user_id,
        consent_recorded=memory.consent_fingerprint is not None,
        expires_at=memory.expires_at,
        expired=memory_is_expired(memory),
        created_at=memory.created_at,
    )


@router.get("/{agent_id}/memory-policy", response_model=AgentMemoryPolicyResponse)
async def get_agent_memory_policy(
    agent_id: UUID,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> AgentMemoryPolicyResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    policy = await _memory_policy(database, company_id=context.company_id, agent_id=agent_id)
    scope_policies = await _memory_scope_policies(
        database, company_id=context.company_id, agent_id=agent_id
    )
    return _policy_response(agent_id, policy, scope_policies)


@router.put("/{agent_id}/memory-policy", response_model=AgentMemoryPolicyResponse)
async def update_agent_memory_policy(
    agent_id: UUID,
    payload: AgentMemoryPolicyUpdate,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> AgentMemoryPolicyResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    policy = await _memory_policy(database, company_id=context.company_id, agent_id=agent_id)
    if policy is None:
        policy = AgentMemoryPolicy(
            company_id=context.company_id,
            agent_id=agent_id,
            updated_by_user_id=context.user_id,
        )
        database.add(policy)
    for field, value in payload.model_dump(exclude={"scope_policies"}).items():
        setattr(policy, field, value)
    existing_scope_policies = await _memory_scope_policies(
        database, company_id=context.company_id, agent_id=agent_id
    )
    existing_by_scope = {item.scope: item for item in existing_scope_policies}
    requested_scopes = {item.scope for item in payload.scope_policies}
    for existing in existing_scope_policies:
        if existing.scope not in requested_scopes:
            await database.delete(existing)
    saved_scope_policies: list[AgentMemoryScopePolicy] = []
    for item in payload.scope_policies:
        scope_policy = existing_by_scope.get(item.scope)
        if scope_policy is None:
            scope_policy = AgentMemoryScopePolicy(
                company_id=context.company_id,
                agent_id=agent_id,
                scope=item.scope,
                retention_days=item.retention_days,
                retrieval_enabled=item.retrieval_enabled,
            )
            database.add(scope_policy)
        else:
            scope_policy.retention_days = item.retention_days
            scope_policy.retrieval_enabled = item.retrieval_enabled
        saved_scope_policies.append(scope_policy)
    policy.updated_by_user_id = context.user_id
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.memory_policy.updated",
        target_type="agent",
        target_id=agent_id,
        details={
            "default_retention_days": payload.default_retention_days,
            "max_retention_days": payload.max_retention_days,
            "allowed_scopes": payload.allowed_scopes,
            "allowed_classifications": payload.allowed_classifications,
            "max_context_tokens": payload.max_context_tokens,
            "scope_policy_count": len(payload.scope_policies),
        },
    )
    await database.commit()
    await database.refresh(policy)
    return _policy_response(agent_id, policy, saved_scope_policies)


@router.get("/{agent_id}/memories", response_model=list[AgentMemoryResponse])
async def list_agent_memories(
    agent_id: UUID,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
    include_expired: bool = Query(default=False),
) -> list[AgentMemoryResponse]:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    statement = select(AgentMemoryEntry).where(
        AgentMemoryEntry.company_id == context.company_id,
        AgentMemoryEntry.agent_id == agent_id,
    )
    if not include_expired:
        statement = statement.where(AgentMemoryEntry.expires_at > utc_now())
    rows = list(
        await database.scalars(statement.order_by(AgentMemoryEntry.created_at.desc()).limit(200))
    )
    return [_memory_response(row) for row in rows]


@router.post(
    "/{agent_id}/memories",
    response_model=AgentMemoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_memory(
    agent_id: UUID,
    payload: AgentMemoryCreate,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
    settings: RequestSettings,
) -> AgentMemoryResponse:
    context = get_request_context(principal)
    agent = await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    if not agent.memory_enabled:
        raise HTTPException(status_code=409, detail="A memória deste agente está desativada.")
    policy = await _memory_policy(database, company_id=context.company_id, agent_id=agent_id)
    scope_policies = await _memory_scope_policies(
        database, company_id=context.company_id, agent_id=agent_id
    )
    values = memory_policy_values(policy, scope_policies)
    if payload.scope not in cast(list[str], values["allowed_scopes"]):
        raise HTTPException(status_code=422, detail="Este escopo não é permitido pela política.")
    if payload.classification not in cast(list[str], values["allowed_classifications"]):
        raise HTTPException(
            status_code=422, detail="Esta classificação não é permitida pela política."
        )
    if payload.scope == "user" and payload.subject_user_id is None:
        raise HTTPException(status_code=422, detail="Memórias pessoais exigem um titular.")
    if payload.scope != "user" and payload.subject_user_id is not None:
        raise HTTPException(
            status_code=422, detail="Somente memórias pessoais podem possuir titular."
        )
    subject_membership = None
    if payload.subject_user_id is not None:
        subject_membership = await _active_company_user(
            database, company_id=context.company_id, user_id=payload.subject_user_id
        )
    if (
        payload.scope == "user"
        and cast(bool, values["require_consent_for_user_scope"])
        and not payload.consent_reference
    ):
        raise HTTPException(
            status_code=422,
            detail="Memórias pessoais exigem uma referência de consentimento.",
        )
    effective_scope = next(
        (
            item
            for item in cast(list[dict[str, object]], values["scope_policies"])
            if item["scope"] == payload.scope
        ),
        None,
    )
    retention_days = payload.retention_days or cast(
        int,
        effective_scope["retention_days"]
        if effective_scope is not None
        else values["default_retention_days"],
    )
    if retention_days > cast(int, values["max_retention_days"]):
        raise HTTPException(status_code=422, detail="A retenção supera o limite da política.")
    fingerprint = memory_content_fingerprint(
        secret=settings.encryption_key,
        company_id=context.company_id,
        agent_id=agent_id,
        scope=payload.scope,
        subject_user_id=payload.subject_user_id,
        content=payload.content,
    )
    consent_fingerprint = (
        memory_consent_fingerprint(
            secret=settings.encryption_key,
            company_id=context.company_id,
            agent_id=agent_id,
            subject_user_id=payload.subject_user_id,
            reference=payload.consent_reference,
        )
        if payload.subject_user_id is not None and payload.consent_reference
        else None
    )
    if consent_fingerprint is not None:
        revoked = await database.scalar(
            select(AgentMemoryConsentRevocation.id).where(
                AgentMemoryConsentRevocation.company_id == context.company_id,
                AgentMemoryConsentRevocation.agent_id == agent_id,
                AgentMemoryConsentRevocation.subject_user_id == payload.subject_user_id,
                AgentMemoryConsentRevocation.consent_fingerprint == consent_fingerprint,
            )
        )
        if revoked is not None:
            raise HTTPException(status_code=409, detail="Este consentimento foi revogado.")
    existing = await database.scalar(
        select(AgentMemoryEntry).where(
            AgentMemoryEntry.company_id == context.company_id,
            AgentMemoryEntry.agent_id == agent_id,
            AgentMemoryEntry.content_fingerprint == fingerprint,
        )
    )
    if existing is not None and not memory_is_expired(existing):
        return _memory_response(existing)
    if existing is not None:
        await database.delete(existing)
        await database.flush()
    memory = AgentMemoryEntry(
        company_id=context.company_id,
        agent_id=agent_id,
        created_by_user_id=context.user_id,
        scope=payload.scope,
        classification=payload.classification,
        encrypted_content=CredentialVault(settings.encryption_key).encrypt(
            {"content": payload.content}
        ),
        content_fingerprint=fingerprint,
        source_type=payload.source_type,
        source_id=payload.source_id,
        subject_user_id=payload.subject_user_id,
        subject_membership_id=subject_membership.id if subject_membership else None,
        consent_fingerprint=consent_fingerprint,
        expires_at=utc_now() + timedelta(days=retention_days),
    )
    database.add(memory)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.memory.created",
        target_type="agent_memory",
        target_id=memory.id,
        details={
            "agent_id": str(agent_id),
            "scope": memory.scope,
            "classification": memory.classification,
            "expires_at": memory.expires_at.isoformat(),
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.memory.created",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="confidential",
            payload={"agent_id": str(agent_id), "memory_id": str(memory.id)},
        ),
    )
    await database.commit()
    await database.refresh(memory)
    return _memory_response(memory)


@router.post(
    "/{agent_id}/memory-consent-revocations",
    response_model=AgentMemoryConsentRevocationResponse,
)
async def revoke_agent_memory_consent(
    agent_id: UUID,
    payload: AgentMemoryConsentRevoke,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
    settings: RequestSettings,
) -> AgentMemoryConsentRevocationResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    subject_membership = await _active_company_user(
        database, company_id=context.company_id, user_id=payload.subject_user_id
    )
    fingerprint = memory_consent_fingerprint(
        secret=settings.encryption_key,
        company_id=context.company_id,
        agent_id=agent_id,
        subject_user_id=payload.subject_user_id,
        reference=payload.consent_reference,
    )
    revocation = await database.scalar(
        select(AgentMemoryConsentRevocation).where(
            AgentMemoryConsentRevocation.company_id == context.company_id,
            AgentMemoryConsentRevocation.agent_id == agent_id,
            AgentMemoryConsentRevocation.subject_user_id == payload.subject_user_id,
            AgentMemoryConsentRevocation.consent_fingerprint == fingerprint,
        )
    )
    already_revoked = revocation is not None
    if revocation is None:
        revocation = AgentMemoryConsentRevocation(
            company_id=context.company_id,
            agent_id=agent_id,
            subject_user_id=payload.subject_user_id,
            subject_membership_id=subject_membership.id,
            consent_fingerprint=fingerprint,
            revoked_by_user_id=context.user_id,
        )
        database.add(revocation)
        await database.flush()
    memories = list(
        await database.scalars(
            select(AgentMemoryEntry)
            .where(
                AgentMemoryEntry.company_id == context.company_id,
                AgentMemoryEntry.agent_id == agent_id,
                AgentMemoryEntry.subject_user_id == payload.subject_user_id,
                AgentMemoryEntry.consent_fingerprint == fingerprint,
            )
            .with_for_update()
        )
    )
    for memory in memories:
        await database.delete(memory)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.memory_consent.revoked",
        target_type="agent_memory_consent_revocation",
        target_id=revocation.id,
        details={"agent_id": str(agent_id), "deleted_count": len(memories)},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.memory_consent.revoked",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="confidential",
            payload={
                "agent_id": str(agent_id),
                "revocation_id": str(revocation.id),
                "deleted_count": len(memories),
            },
        ),
    )
    await database.commit()
    return AgentMemoryConsentRevocationResponse(
        revocation_id=revocation.id,
        deleted_count=len(memories),
        already_revoked=already_revoked,
    )


@router.delete("/{agent_id}/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_memory(
    agent_id: UUID,
    memory_id: UUID,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> Response:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    memory = await database.scalar(
        select(AgentMemoryEntry).where(
            AgentMemoryEntry.id == memory_id,
            AgentMemoryEntry.company_id == context.company_id,
            AgentMemoryEntry.agent_id == agent_id,
        )
    )
    if memory is None:
        raise HTTPException(status_code=404, detail="Memória não encontrada.")
    await database.delete(memory)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.memory.deleted",
        target_type="agent_memory",
        target_id=memory_id,
        details={"agent_id": str(agent_id)},
    )
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{agent_id}/memory-purge", response_model=AgentMemoryPurgeResponse)
async def purge_agent_memories(
    agent_id: UUID,
    payload: AgentMemoryPurgeRequest,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> AgentMemoryPurgeResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    statement = select(AgentMemoryEntry).where(
        AgentMemoryEntry.company_id == context.company_id,
        AgentMemoryEntry.agent_id == agent_id,
    )
    if payload.expired_only:
        statement = statement.where(AgentMemoryEntry.expires_at <= utc_now())
    rows = list(await database.scalars(statement.with_for_update()))
    for memory in rows:
        await database.delete(memory)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.memory.purged",
        target_type="agent",
        target_id=agent_id,
        details={"expired_only": payload.expired_only, "deleted_count": len(rows)},
    )
    await database.commit()
    return AgentMemoryPurgeResponse(deleted_count=len(rows))
