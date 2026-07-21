from __future__ import annotations

from datetime import timedelta
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_, select

from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.agents.coordination_models import AgentDelegation
from app.modules.agents.memory_models import (
    AgentMemoryConsentRevocation,
    AgentMemoryEntry,
    AgentMemoryLegalHold,
    AgentMemoryPolicy,
    AgentMemoryPurposePolicy,
    AgentMemoryScopePolicy,
    AgentTaskMemoryAccessGrant,
    AgentTaskMemoryAccessTrace,
)
from app.modules.agents.memory_schemas import (
    AgentMemoryConsentRevocationResponse,
    AgentMemoryConsentRevoke,
    AgentMemoryCreate,
    AgentMemoryLegalHoldCreate,
    AgentMemoryLegalHoldDecision,
    AgentMemoryLegalHoldResponse,
    AgentMemoryMetadataExport,
    AgentMemoryPolicyResponse,
    AgentMemoryPolicyUpdate,
    AgentMemoryPurgeRequest,
    AgentMemoryPurgeResponse,
    AgentMemoryPurposePolicyInput,
    AgentMemoryResponse,
    AgentMemoryScopePolicyInput,
    AgentTaskMemoryAccessGrantCreate,
    AgentTaskMemoryAccessGrantResponse,
    AgentTaskMemoryAccessRevoke,
    AgentTaskMemoryAccessTraceResponse,
    AgentTaskMemoryContextItem,
    AgentTaskMemoryContextRequest,
    AgentTaskMemoryContextResponse,
    LegalHoldStatus,
    MemoryClassification,
    MemoryPurpose,
    MemoryScope,
    MemorySource,
    TaskMemoryAccessStatus,
    TaskMemoryTraceOutcome,
)
from app.modules.agents.memory_service import (
    has_active_memory_legal_hold,
    memory_access_revocation_fingerprint,
    memory_consent_fingerprint,
    memory_content_fingerprint,
    memory_is_expired,
    memory_legal_reference_fingerprint,
    memory_policy_values,
    retrieve_shared_task_memories,
)
from app.modules.agents.models import Agent
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.plugins.crypto import CredentialVault
from app.modules.users.models import CompanyUser

router = APIRouter()
CanConfigureAgentMemory = Annotated[Principal, Depends(require_permission("agents.configure"))]
CanExecuteAgentMemory = Annotated[Principal, Depends(require_permission("agents.execute"))]


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


async def _memory_purpose_policies(
    database: DatabaseSession, *, company_id: UUID, agent_id: UUID
) -> list[AgentMemoryPurposePolicy]:
    return list(
        await database.scalars(
            select(AgentMemoryPurposePolicy).where(
                AgentMemoryPurposePolicy.company_id == company_id,
                AgentMemoryPurposePolicy.agent_id == agent_id,
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
    purpose_policies: list[AgentMemoryPurposePolicy],
) -> AgentMemoryPolicyResponse:
    values = memory_policy_values(policy, scope_policies, purpose_policies)
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
        purpose_policies=[
            AgentMemoryPurposePolicyInput.model_validate(item)
            for item in cast(list[dict[str, object]], values["purpose_policies"])
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
        task_delegation_id=memory.task_delegation_id,
        purpose=cast(MemoryPurpose, memory.purpose),
        subject_user_id=memory.subject_user_id,
        consent_recorded=memory.consent_fingerprint is not None,
        expires_at=memory.expires_at,
        expired=memory_is_expired(memory),
        created_at=memory.created_at,
    )


async def _active_task_delegation(
    database: DatabaseSession,
    *,
    company_id: UUID,
    agent_id: UUID,
    delegation_id: UUID,
) -> AgentDelegation:
    delegation = await database.scalar(
        select(AgentDelegation).where(
            AgentDelegation.id == delegation_id,
            AgentDelegation.company_id == company_id,
            or_(
                AgentDelegation.supervisor_agent_id == agent_id,
                AgentDelegation.assigned_agent_id == agent_id,
            ),
            AgentDelegation.status.in_(("queued", "in_progress", "awaiting_approval")),
        )
    )
    if delegation is None:
        raise HTTPException(status_code=404, detail="Delegação ativa não encontrada.")
    return delegation


def _legal_hold_response(hold: AgentMemoryLegalHold) -> AgentMemoryLegalHoldResponse:
    effective_status = "expired" if hold.expires_at <= utc_now() else hold.status
    return AgentMemoryLegalHoldResponse(
        id=hold.id,
        agent_id=hold.agent_id,
        task_delegation_id=hold.task_delegation_id,
        reason_code=hold.reason_code,
        retention_days=hold.retention_days,
        status=cast(LegalHoldStatus, effective_status),
        requested_by_user_id=hold.requested_by_user_id,
        decided_by_user_id=hold.decided_by_user_id,
        expires_at=hold.expires_at,
        created_at=hold.created_at,
        decided_at=hold.decided_at,
    )


def _task_memory_access_response(
    grant: AgentTaskMemoryAccessGrant,
) -> AgentTaskMemoryAccessGrantResponse:
    effective_status = "expired" if grant.expires_at <= utc_now() else grant.status
    return AgentTaskMemoryAccessGrantResponse(
        id=grant.id,
        task_delegation_id=grant.task_delegation_id,
        owner_agent_id=grant.owner_agent_id,
        recipient_agent_id=grant.recipient_agent_id,
        purpose=grant.purpose,
        allowed_classifications=grant.allowed_classifications,
        max_entries=grant.max_entries,
        max_content_characters=grant.max_content_characters,
        status=cast(TaskMemoryAccessStatus, effective_status),
        granted_by_user_id=grant.granted_by_user_id,
        revoked_by_user_id=grant.revoked_by_user_id,
        expires_at=grant.expires_at,
        created_at=grant.created_at,
        revoked_at=grant.revoked_at,
    )


def _task_memory_trace_response(
    trace: AgentTaskMemoryAccessTrace,
) -> AgentTaskMemoryAccessTraceResponse:
    return AgentTaskMemoryAccessTraceResponse(
        id=trace.id,
        grant_id=trace.grant_id,
        task_delegation_id=trace.task_delegation_id,
        agent_run_id=trace.agent_run_id,
        owner_agent_id=trace.owner_agent_id,
        recipient_agent_id=trace.recipient_agent_id,
        outcome=cast(TaskMemoryTraceOutcome, trace.outcome),
        item_count=trace.item_count,
        total_characters=trace.total_characters,
        blocked_items=trace.blocked_items,
        created_at=trace.created_at,
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
    purpose_policies = await _memory_purpose_policies(
        database, company_id=context.company_id, agent_id=agent_id
    )
    return _policy_response(agent_id, policy, scope_policies, purpose_policies)


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
    for field, value in payload.model_dump(exclude={"scope_policies", "purpose_policies"}).items():
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
    existing_purpose_policies = await _memory_purpose_policies(
        database, company_id=context.company_id, agent_id=agent_id
    )
    existing_by_purpose = {item.purpose: item for item in existing_purpose_policies}
    requested_purposes = {item.purpose for item in payload.purpose_policies}
    for existing_purpose in existing_purpose_policies:
        if existing_purpose.purpose not in requested_purposes:
            await database.delete(existing_purpose)
    saved_purpose_policies: list[AgentMemoryPurposePolicy] = []
    for purpose_item in payload.purpose_policies:
        purpose_policy = existing_by_purpose.get(purpose_item.purpose)
        if purpose_policy is None:
            purpose_policy = AgentMemoryPurposePolicy(
                company_id=context.company_id,
                agent_id=agent_id,
                purpose=purpose_item.purpose,
                retention_days=purpose_item.retention_days,
                enabled=purpose_item.enabled,
            )
            database.add(purpose_policy)
        else:
            purpose_policy.retention_days = purpose_item.retention_days
            purpose_policy.enabled = purpose_item.enabled
        saved_purpose_policies.append(purpose_policy)
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
            "purpose_policy_count": len(payload.purpose_policies),
        },
    )
    await database.commit()
    await database.refresh(policy)
    return _policy_response(agent_id, policy, saved_scope_policies, saved_purpose_policies)


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
    purpose_policies = await _memory_purpose_policies(
        database, company_id=context.company_id, agent_id=agent_id
    )
    values = memory_policy_values(policy, scope_policies, purpose_policies)
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
    task_delegation = None
    if payload.task_delegation_id is not None:
        task_delegation = await _active_task_delegation(
            database,
            company_id=context.company_id,
            agent_id=agent_id,
            delegation_id=payload.task_delegation_id,
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
    effective_purpose = next(
        (
            item
            for item in cast(list[dict[str, object]], values["purpose_policies"])
            if item["purpose"] == payload.purpose
        ),
        None,
    )
    if effective_purpose is None or not bool(effective_purpose["enabled"]):
        raise HTTPException(status_code=422, detail="Esta finalidade não é permitida.")
    scope_retention = cast(
        int,
        effective_scope["retention_days"]
        if effective_scope is not None
        else values["default_retention_days"],
    )
    purpose_retention = cast(int, effective_purpose["retention_days"])
    retention_limit = min(
        scope_retention, purpose_retention, cast(int, values["max_retention_days"])
    )
    retention_days = payload.retention_days or retention_limit
    if retention_days > retention_limit:
        raise HTTPException(
            status_code=422,
            detail="A retenção supera o limite do escopo ou da finalidade.",
        )
    fingerprint = memory_content_fingerprint(
        secret=settings.encryption_key,
        company_id=context.company_id,
        agent_id=agent_id,
        scope=payload.scope,
        purpose=payload.purpose,
        subject_user_id=payload.subject_user_id,
        task_delegation_id=payload.task_delegation_id,
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
        source_type="task" if task_delegation is not None else payload.source_type,
        source_id=str(task_delegation.id) if task_delegation is not None else payload.source_id,
        task_delegation_id=task_delegation.id if task_delegation is not None else None,
        purpose=payload.purpose,
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
            "task_delegation_id": str(memory.task_delegation_id)
            if memory.task_delegation_id
            else None,
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


@router.get(
    "/{agent_id}/delegations/{delegation_id}/memory-legal-holds",
    response_model=list[AgentMemoryLegalHoldResponse],
)
async def list_agent_memory_legal_holds(
    agent_id: UUID,
    delegation_id: UUID,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> list[AgentMemoryLegalHoldResponse]:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    holds = list(
        await database.scalars(
            select(AgentMemoryLegalHold)
            .where(
                AgentMemoryLegalHold.company_id == context.company_id,
                AgentMemoryLegalHold.agent_id == agent_id,
                AgentMemoryLegalHold.task_delegation_id == delegation_id,
            )
            .order_by(AgentMemoryLegalHold.created_at.desc())
        )
    )
    return [_legal_hold_response(hold) for hold in holds]


@router.post(
    "/{agent_id}/delegations/{delegation_id}/memory-legal-holds",
    response_model=AgentMemoryLegalHoldResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_agent_memory_legal_hold(
    agent_id: UUID,
    delegation_id: UUID,
    payload: AgentMemoryLegalHoldCreate,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
    settings: RequestSettings,
) -> AgentMemoryLegalHoldResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    await _active_task_delegation(
        database,
        company_id=context.company_id,
        agent_id=agent_id,
        delegation_id=delegation_id,
    )
    existing = await database.scalar(
        select(AgentMemoryLegalHold)
        .where(
            AgentMemoryLegalHold.company_id == context.company_id,
            AgentMemoryLegalHold.agent_id == agent_id,
            AgentMemoryLegalHold.task_delegation_id == delegation_id,
            AgentMemoryLegalHold.status.in_(("pending", "approved")),
            AgentMemoryLegalHold.expires_at > utc_now(),
        )
        .with_for_update()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="A delegação já possui retenção legal ativa.")
    hold = AgentMemoryLegalHold(
        company_id=context.company_id,
        agent_id=agent_id,
        task_delegation_id=delegation_id,
        reason_code=payload.reason_code,
        legal_reference_fingerprint=memory_legal_reference_fingerprint(
            secret=settings.encryption_key,
            company_id=context.company_id,
            agent_id=agent_id,
            delegation_id=delegation_id,
            reference=payload.legal_reference,
        ),
        retention_days=payload.retention_days,
        requested_by_user_id=context.user_id,
        expires_at=utc_now() + timedelta(days=payload.retention_days),
    )
    database.add(hold)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.memory_legal_hold.requested",
        target_type="agent_memory_legal_hold",
        target_id=hold.id,
        details={
            "agent_id": str(agent_id),
            "delegation_id": str(delegation_id),
            "reason_code": hold.reason_code,
            "retention_days": hold.retention_days,
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.memory_legal_hold.requested",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="confidential",
            payload={"hold_id": str(hold.id), "delegation_id": str(delegation_id)},
        ),
    )
    await database.commit()
    await database.refresh(hold)
    return _legal_hold_response(hold)


@router.post(
    "/{agent_id}/delegations/{delegation_id}/memory-legal-holds/{hold_id}/decision",
    response_model=AgentMemoryLegalHoldResponse,
)
async def decide_agent_memory_legal_hold(
    agent_id: UUID,
    delegation_id: UUID,
    hold_id: UUID,
    payload: AgentMemoryLegalHoldDecision,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> AgentMemoryLegalHoldResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    hold = await database.scalar(
        select(AgentMemoryLegalHold)
        .where(
            AgentMemoryLegalHold.id == hold_id,
            AgentMemoryLegalHold.company_id == context.company_id,
            AgentMemoryLegalHold.agent_id == agent_id,
            AgentMemoryLegalHold.task_delegation_id == delegation_id,
        )
        .with_for_update()
    )
    if hold is None:
        raise HTTPException(status_code=404, detail="Retenção legal não encontrada.")
    if hold.status != "pending" or hold.expires_at <= utc_now():
        raise HTTPException(status_code=409, detail="A retenção legal não está pendente.")
    if hold.requested_by_user_id == context.user_id:
        raise HTTPException(status_code=409, detail="A solicitação exige aprovação independente.")
    await _active_task_delegation(
        database,
        company_id=context.company_id,
        agent_id=agent_id,
        delegation_id=delegation_id,
    )
    hold.status = payload.decision
    hold.decided_by_user_id = context.user_id
    hold.decided_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action=f"agent.memory_legal_hold.{payload.decision}",
        target_type="agent_memory_legal_hold",
        target_id=hold.id,
        details={"agent_id": str(agent_id), "delegation_id": str(delegation_id)},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=f"agent.memory_legal_hold.{payload.decision}",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="confidential",
            payload={"hold_id": str(hold.id), "delegation_id": str(delegation_id)},
        ),
    )
    await database.commit()
    await database.refresh(hold)
    return _legal_hold_response(hold)


@router.get(
    "/{agent_id}/delegations/{delegation_id}/memory-access-grants",
    response_model=list[AgentTaskMemoryAccessGrantResponse],
)
async def list_agent_task_memory_access_grants(
    agent_id: UUID,
    delegation_id: UUID,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> list[AgentTaskMemoryAccessGrantResponse]:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    await _active_task_delegation(
        database,
        company_id=context.company_id,
        agent_id=agent_id,
        delegation_id=delegation_id,
    )
    grants = list(
        await database.scalars(
            select(AgentTaskMemoryAccessGrant)
            .where(
                AgentTaskMemoryAccessGrant.company_id == context.company_id,
                AgentTaskMemoryAccessGrant.task_delegation_id == delegation_id,
                AgentTaskMemoryAccessGrant.owner_agent_id == agent_id,
            )
            .order_by(AgentTaskMemoryAccessGrant.created_at.desc())
        )
    )
    return [_task_memory_access_response(grant) for grant in grants]


@router.post(
    "/{agent_id}/delegations/{delegation_id}/memory-access-grants",
    response_model=AgentTaskMemoryAccessGrantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_task_memory_access_grant(
    agent_id: UUID,
    delegation_id: UUID,
    payload: AgentTaskMemoryAccessGrantCreate,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> AgentTaskMemoryAccessGrantResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    await _tenant_agent(
        database,
        company_id=context.company_id,
        agent_id=payload.recipient_agent_id,
    )
    delegation = await _active_task_delegation(
        database,
        company_id=context.company_id,
        agent_id=agent_id,
        delegation_id=delegation_id,
    )
    participants = {delegation.supervisor_agent_id, delegation.assigned_agent_id}
    if payload.recipient_agent_id == agent_id or payload.recipient_agent_id not in participants:
        raise HTTPException(
            status_code=422,
            detail="O destinatário deve ser o outro agente participante da tarefa.",
        )
    policy = await _memory_policy(database, company_id=context.company_id, agent_id=agent_id)
    scope_policies = await _memory_scope_policies(
        database, company_id=context.company_id, agent_id=agent_id
    )
    purpose_policies = await _memory_purpose_policies(
        database, company_id=context.company_id, agent_id=agent_id
    )
    policy_values = memory_policy_values(policy, scope_policies, purpose_policies)
    if not set(payload.allowed_classifications).issubset(
        set(cast(list[str], policy_values["allowed_classifications"]))
    ):
        raise HTTPException(
            status_code=422,
            detail="O contrato tenta compartilhar classificação não autorizada pela política.",
        )
    normalized_classifications = sorted(payload.allowed_classifications)
    existing = await database.scalar(
        select(AgentTaskMemoryAccessGrant).where(
            AgentTaskMemoryAccessGrant.company_id == context.company_id,
            AgentTaskMemoryAccessGrant.idempotency_key == payload.idempotency_key,
        )
    )
    if existing is not None:
        same_contract = (
            existing.task_delegation_id == delegation_id
            and existing.owner_agent_id == agent_id
            and existing.recipient_agent_id == payload.recipient_agent_id
            and existing.purpose == payload.purpose
            and sorted(existing.allowed_classifications) == normalized_classifications
            and existing.max_entries == payload.max_entries
            and existing.max_content_characters == payload.max_content_characters
        )
        if not same_contract:
            raise HTTPException(
                status_code=409, detail="Chave idempotente usada por outro contrato."
            )
        return _task_memory_access_response(existing)
    now = utc_now()
    expires_at = min(now + timedelta(minutes=payload.expires_in_minutes), delegation.due_at)
    if expires_at <= now:
        raise HTTPException(
            status_code=409, detail="A tarefa não possui prazo ativo para compartilhar."
        )
    grant = AgentTaskMemoryAccessGrant(
        company_id=context.company_id,
        task_delegation_id=delegation_id,
        owner_agent_id=agent_id,
        recipient_agent_id=payload.recipient_agent_id,
        purpose=payload.purpose,
        allowed_classifications=normalized_classifications,
        max_entries=payload.max_entries,
        max_content_characters=payload.max_content_characters,
        idempotency_key=payload.idempotency_key,
        granted_by_user_id=context.user_id,
        expires_at=expires_at,
    )
    database.add(grant)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.task_memory_access.granted",
        target_type="agent_task_memory_access_grant",
        target_id=grant.id,
        details={
            "delegation_id": str(delegation_id),
            "owner_agent_id": str(agent_id),
            "recipient_agent_id": str(payload.recipient_agent_id),
            "purpose": grant.purpose,
            "max_entries": grant.max_entries,
            "max_content_characters": grant.max_content_characters,
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.task_memory_access.granted",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="confidential",
            payload={"grant_id": str(grant.id), "delegation_id": str(delegation_id)},
        ),
    )
    await database.commit()
    await database.refresh(grant)
    return _task_memory_access_response(grant)


@router.post(
    "/{agent_id}/delegations/{delegation_id}/memory-access-grants/{grant_id}/revoke",
    response_model=AgentTaskMemoryAccessGrantResponse,
)
async def revoke_agent_task_memory_access_grant(
    agent_id: UUID,
    delegation_id: UUID,
    grant_id: UUID,
    payload: AgentTaskMemoryAccessRevoke,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
    settings: RequestSettings,
) -> AgentTaskMemoryAccessGrantResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    grant = await database.scalar(
        select(AgentTaskMemoryAccessGrant)
        .where(
            AgentTaskMemoryAccessGrant.id == grant_id,
            AgentTaskMemoryAccessGrant.company_id == context.company_id,
            AgentTaskMemoryAccessGrant.task_delegation_id == delegation_id,
            AgentTaskMemoryAccessGrant.owner_agent_id == agent_id,
        )
        .with_for_update()
    )
    if grant is None:
        raise HTTPException(status_code=404, detail="Contrato de memória não encontrado.")
    if grant.status == "revoked":
        return _task_memory_access_response(grant)
    if grant.status == "expired" or grant.expires_at <= utc_now():
        grant.status = "expired"
        await database.commit()
        await database.refresh(grant)
        return _task_memory_access_response(grant)
    grant.status = "revoked"
    grant.revoked_by_user_id = context.user_id
    grant.revoked_at = utc_now()
    grant.revocation_reason_fingerprint = memory_access_revocation_fingerprint(
        secret=settings.encryption_key,
        company_id=context.company_id,
        grant_id=grant.id,
        reason=payload.reason,
    )
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.task_memory_access.revoked",
        target_type="agent_task_memory_access_grant",
        target_id=grant.id,
        details={
            "delegation_id": str(delegation_id),
            "recipient_agent_id": str(grant.recipient_agent_id),
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.task_memory_access.revoked",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="confidential",
            payload={"grant_id": str(grant.id), "delegation_id": str(delegation_id)},
        ),
    )
    await database.commit()
    await database.refresh(grant)
    return _task_memory_access_response(grant)


@router.post(
    "/{agent_id}/delegations/{delegation_id}/shared-memory-context",
    response_model=AgentTaskMemoryContextResponse,
)
async def get_agent_shared_task_memory_context(
    agent_id: UUID,
    delegation_id: UUID,
    payload: AgentTaskMemoryContextRequest,
    principal: CanExecuteAgentMemory,
    database: DatabaseSession,
    settings: RequestSettings,
) -> AgentTaskMemoryContextResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    await _active_task_delegation(
        database,
        company_id=context.company_id,
        agent_id=agent_id,
        delegation_id=delegation_id,
    )
    grant = await database.scalar(
        select(AgentTaskMemoryAccessGrant).where(
            AgentTaskMemoryAccessGrant.id == payload.grant_id,
            AgentTaskMemoryAccessGrant.company_id == context.company_id,
            AgentTaskMemoryAccessGrant.task_delegation_id == delegation_id,
            AgentTaskMemoryAccessGrant.recipient_agent_id == agent_id,
            AgentTaskMemoryAccessGrant.purpose == payload.purpose,
            AgentTaskMemoryAccessGrant.status == "active",
            AgentTaskMemoryAccessGrant.expires_at > utc_now(),
        )
    )
    if grant is None:
        raise HTTPException(status_code=404, detail="Contexto compartilhado não autorizado.")
    shared = await retrieve_shared_task_memories(
        database,
        settings=settings,
        company_id=context.company_id,
        grant=grant,
    )
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.task_memory_access.used",
        target_type="agent_task_memory_access_grant",
        target_id=grant.id,
        details={
            "delegation_id": str(delegation_id),
            "recipient_agent_id": str(agent_id),
            "item_count": len(shared.items),
            "total_characters": shared.total_characters,
            "blocked_items": shared.blocked_items,
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.task_memory_access.used",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="confidential",
            payload={
                "grant_id": str(grant.id),
                "delegation_id": str(delegation_id),
                "item_count": len(shared.items),
            },
        ),
    )
    await database.commit()
    return AgentTaskMemoryContextResponse(
        grant_id=grant.id,
        task_delegation_id=delegation_id,
        recipient_agent_id=agent_id,
        purpose=payload.purpose,
        items=[
            AgentTaskMemoryContextItem(
                memory_id=item.memory_id,
                owner_agent_id=item.owner_agent_id,
                classification=cast(MemoryClassification, item.classification),
                purpose=cast(MemoryPurpose, item.purpose),
                content=item.content,
                truncated=item.truncated,
                created_at=item.created_at,
            )
            for item in shared.items
        ],
        total_characters=shared.total_characters,
        blocked_items=shared.blocked_items,
    )


@router.get(
    "/{agent_id}/delegations/{delegation_id}/memory-access-traces",
    response_model=list[AgentTaskMemoryAccessTraceResponse],
)
async def list_agent_task_memory_access_traces(
    agent_id: UUID,
    delegation_id: UUID,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> list[AgentTaskMemoryAccessTraceResponse]:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    delegation = await database.scalar(
        select(AgentDelegation).where(
            AgentDelegation.id == delegation_id,
            AgentDelegation.company_id == context.company_id,
            or_(
                AgentDelegation.supervisor_agent_id == agent_id,
                AgentDelegation.assigned_agent_id == agent_id,
            ),
        )
    )
    if delegation is None:
        raise HTTPException(status_code=404, detail="Delegação não encontrada.")
    traces = list(
        await database.scalars(
            select(AgentTaskMemoryAccessTrace)
            .where(
                AgentTaskMemoryAccessTrace.company_id == context.company_id,
                AgentTaskMemoryAccessTrace.task_delegation_id == delegation_id,
            )
            .order_by(AgentTaskMemoryAccessTrace.created_at.desc())
        )
    )
    return [_task_memory_trace_response(trace) for trace in traces]


@router.get("/{agent_id}/my-memories", response_model=list[AgentMemoryResponse])
async def list_my_agent_memories(
    agent_id: UUID,
    principal: CanExecuteAgentMemory,
    database: DatabaseSession,
) -> list[AgentMemoryResponse]:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    memories = list(
        await database.scalars(
            select(AgentMemoryEntry)
            .where(
                AgentMemoryEntry.company_id == context.company_id,
                AgentMemoryEntry.agent_id == agent_id,
                AgentMemoryEntry.scope == "user",
                AgentMemoryEntry.subject_user_id == context.user_id,
                AgentMemoryEntry.expires_at > utc_now(),
            )
            .order_by(AgentMemoryEntry.created_at.desc())
            .limit(200)
        )
    )
    return [_memory_response(memory) for memory in memories]


@router.get("/{agent_id}/my-memory-export", response_model=AgentMemoryMetadataExport)
async def export_my_agent_memory_metadata(
    agent_id: UUID,
    principal: CanExecuteAgentMemory,
    database: DatabaseSession,
) -> AgentMemoryMetadataExport:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    memories = list(
        await database.scalars(
            select(AgentMemoryEntry)
            .where(
                AgentMemoryEntry.company_id == context.company_id,
                AgentMemoryEntry.agent_id == agent_id,
                AgentMemoryEntry.scope == "user",
                AgentMemoryEntry.subject_user_id == context.user_id,
                AgentMemoryEntry.expires_at > utc_now(),
            )
            .order_by(AgentMemoryEntry.created_at.desc())
            .limit(200)
        )
    )
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.memory_metadata.exported",
        target_type="agent",
        target_id=agent_id,
        details={"record_count": len(memories)},
    )
    await database.commit()
    return AgentMemoryMetadataExport(
        agent_id=agent_id,
        generated_at=utc_now(),
        total=len(memories),
        memories=[_memory_response(memory) for memory in memories],
    )


@router.delete("/{agent_id}/my-memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_agent_memory(
    agent_id: UUID,
    memory_id: UUID,
    principal: CanExecuteAgentMemory,
    database: DatabaseSession,
) -> Response:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    memory = await database.scalar(
        select(AgentMemoryEntry).where(
            AgentMemoryEntry.id == memory_id,
            AgentMemoryEntry.company_id == context.company_id,
            AgentMemoryEntry.agent_id == agent_id,
            AgentMemoryEntry.scope == "user",
            AgentMemoryEntry.subject_user_id == context.user_id,
        )
    )
    if memory is None:
        raise HTTPException(status_code=404, detail="Memória pessoal não encontrada.")
    await database.delete(memory)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.personal_memory.deleted",
        target_type="agent_memory",
        target_id=memory_id,
        details={"agent_id": str(agent_id)},
    )
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    if memory.task_delegation_id is not None and await has_active_memory_legal_hold(
        database,
        company_id=context.company_id,
        agent_id=agent_id,
        delegation_id=memory.task_delegation_id,
    ):
        raise HTTPException(status_code=409, detail="A memória possui retenção legal aprovada.")
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
    deleted_count = 0
    for memory in rows:
        if memory.task_delegation_id is not None and await has_active_memory_legal_hold(
            database,
            company_id=context.company_id,
            agent_id=agent_id,
            delegation_id=memory.task_delegation_id,
        ):
            continue
        await database.delete(memory)
        deleted_count += 1
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.memory.purged",
        target_type="agent",
        target_id=agent_id,
        details={"expired_only": payload.expired_only, "deleted_count": deleted_count},
    )
    await database.commit()
    return AgentMemoryPurgeResponse(deleted_count=deleted_count)
