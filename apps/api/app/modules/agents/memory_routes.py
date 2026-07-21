from __future__ import annotations

import json
from datetime import timedelta
from hmac import compare_digest
from typing import Annotated, Literal, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, func, or_, select

from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.agents.coordination_models import AgentDelegation, AgentTaskContract
from app.modules.agents.memory_models import (
    AgentMemoryConsentRevocation,
    AgentMemoryEntry,
    AgentMemoryExerciseSchedule,
    AgentMemoryLegalHold,
    AgentMemoryPolicy,
    AgentMemoryPurposePolicy,
    AgentMemoryResponseExercise,
    AgentMemoryRiskReportRecord,
    AgentMemoryRiskSigningKeyVersion,
    AgentMemoryScopePolicy,
    AgentTaskMemoryAccessGrant,
    AgentTaskMemoryAccessIncident,
    AgentTaskMemoryAccessTrace,
    AgentTaskMemoryIncidentReviewRecord,
)
from app.modules.agents.memory_schemas import (
    AgentMemoryConsentRevocationResponse,
    AgentMemoryConsentRevoke,
    AgentMemoryCreate,
    AgentMemoryExerciseDueResponse,
    AgentMemoryExerciseScheduleResponse,
    AgentMemoryExerciseScheduleUpdate,
    AgentMemoryIncidentEscalationResponse,
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
    AgentMemoryResponseExerciseCreate,
    AgentMemoryResponseExerciseResponse,
    AgentMemoryRiskReport,
    AgentMemoryRiskReportPayload,
    AgentMemoryRiskReportVerification,
    AgentMemoryRiskSigningKeyResponse,
    AgentMemoryRiskSummary,
    AgentMemoryScopePolicyInput,
    AgentTaskMemoryAccessDecision,
    AgentTaskMemoryAccessGrantCreate,
    AgentTaskMemoryAccessGrantResponse,
    AgentTaskMemoryAccessRevoke,
    AgentTaskMemoryAccessTraceResponse,
    AgentTaskMemoryContextItem,
    AgentTaskMemoryContextRequest,
    AgentTaskMemoryContextResponse,
    AgentTaskMemoryIncidentResponse,
    AgentTaskMemoryIncidentReview,
    AgentTaskMemoryIncidentRevoke,
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
    memory_incident_value_fingerprint,
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
        max_shared_context_entries=cast(int, values["max_shared_context_entries"]),
        max_shared_context_characters=cast(int, values["max_shared_context_characters"]),
        blocked_context_alert_threshold=cast(int, values["blocked_context_alert_threshold"]),
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
        allowed_tool_keys=grant.allowed_tool_keys,
        max_classification=cast(MemoryClassification, grant.max_classification),
        max_cost_microunits=grant.max_cost_microunits,
        requires_human_approval=grant.requires_human_approval,
        approval_status=(
            "expired"
            if grant.requires_human_approval
            and grant.approval_expires_at is not None
            and grant.approval_expires_at <= utc_now()
            else grant.approval_status
        ),
        approval_ttl_minutes=grant.approval_ttl_minutes,
        max_entries=grant.max_entries,
        max_content_characters=grant.max_content_characters,
        status=cast(TaskMemoryAccessStatus, effective_status),
        granted_by_user_id=grant.granted_by_user_id,
        approved_by_user_id=grant.approved_by_user_id,
        revoked_by_user_id=grant.revoked_by_user_id,
        expires_at=grant.expires_at,
        created_at=grant.created_at,
        approval_decided_at=grant.approval_decided_at,
        approval_expires_at=grant.approval_expires_at,
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
        estimated_cost_microunits=trace.estimated_cost_microunits,
        created_at=trace.created_at,
    )


def _task_memory_incident_response(
    incident: AgentTaskMemoryAccessIncident, *, already_processed: bool = False
) -> AgentTaskMemoryIncidentResponse:
    return AgentTaskMemoryIncidentResponse(
        id=incident.id,
        agent_id=incident.owner_agent_id,
        revoked_grants=incident.revoked_grants,
        quarantine_minutes=incident.quarantine_minutes,
        quarantine_until=incident.quarantine_until,
        quarantined=incident.quarantine_until > utc_now(),
        review_status=incident.review_status,
        severity=incident.severity,
        required_review_quorum=incident.required_review_quorum,
        review_count=incident.review_count,
        review_sla_minutes=incident.review_sla_minutes,
        review_due_at=incident.review_due_at,
        sla_breached=incident.review_status == "pending" and incident.review_due_at <= utc_now(),
        escalation_count=incident.escalation_count,
        escalated_at=incident.escalated_at,
        triggered_by_user_id=incident.triggered_by_user_id,
        reviewed_by_user_id=incident.reviewed_by_user_id,
        reviewed_at=incident.reviewed_at,
        already_processed=already_processed,
        created_at=incident.created_at,
    )


def _canonical_risk_report(payload: AgentMemoryRiskReportPayload) -> str:
    return json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
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
            "max_shared_context_entries": payload.max_shared_context_entries,
            "max_shared_context_characters": payload.max_shared_context_characters,
            "blocked_context_alert_threshold": payload.blocked_context_alert_threshold,
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


@router.get(
    "/{agent_id}/memory-risk-summary",
    response_model=AgentMemoryRiskSummary,
)
async def get_agent_memory_risk_summary(
    agent_id: UUID,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> AgentMemoryRiskSummary:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    now = utc_now()
    active_grants = int(
        await database.scalar(
            select(func.count(AgentTaskMemoryAccessGrant.id)).where(
                AgentTaskMemoryAccessGrant.company_id == context.company_id,
                AgentTaskMemoryAccessGrant.owner_agent_id == agent_id,
                AgentTaskMemoryAccessGrant.status == "active",
                AgentTaskMemoryAccessGrant.expires_at > now,
            )
        )
        or 0
    )
    restricted_active_grants = int(
        await database.scalar(
            select(func.count(AgentTaskMemoryAccessGrant.id)).where(
                AgentTaskMemoryAccessGrant.company_id == context.company_id,
                AgentTaskMemoryAccessGrant.owner_agent_id == agent_id,
                AgentTaskMemoryAccessGrant.status == "active",
                AgentTaskMemoryAccessGrant.expires_at > now,
                AgentTaskMemoryAccessGrant.max_classification == "restricted",
                AgentTaskMemoryAccessGrant.approval_status == "approved",
                AgentTaskMemoryAccessGrant.approval_expires_at > now,
            )
        )
        or 0
    )
    pending_approvals = int(
        await database.scalar(
            select(func.count(AgentTaskMemoryAccessGrant.id)).where(
                AgentTaskMemoryAccessGrant.company_id == context.company_id,
                AgentTaskMemoryAccessGrant.owner_agent_id == agent_id,
                AgentTaskMemoryAccessGrant.status == "active",
                AgentTaskMemoryAccessGrant.approval_status == "pending",
                AgentTaskMemoryAccessGrant.approval_expires_at > now,
            )
        )
        or 0
    )
    expired_approvals = int(
        await database.scalar(
            select(func.count(AgentTaskMemoryAccessGrant.id)).where(
                AgentTaskMemoryAccessGrant.company_id == context.company_id,
                AgentTaskMemoryAccessGrant.owner_agent_id == agent_id,
                AgentTaskMemoryAccessGrant.status == "active",
                AgentTaskMemoryAccessGrant.approval_status.in_(("pending", "approved")),
                AgentTaskMemoryAccessGrant.approval_expires_at <= now,
            )
        )
        or 0
    )
    last_24h = now - timedelta(hours=24)
    blocked_events = int(
        await database.scalar(
            select(func.count(AgentTaskMemoryAccessTrace.id)).where(
                AgentTaskMemoryAccessTrace.company_id == context.company_id,
                AgentTaskMemoryAccessTrace.owner_agent_id == agent_id,
                AgentTaskMemoryAccessTrace.created_at >= last_24h,
                AgentTaskMemoryAccessTrace.outcome.in_(
                    ("blocked", "tool_policy_denied", "aggregate_limit_denied")
                ),
            )
        )
        or 0
    )
    cost_denials = int(
        await database.scalar(
            select(func.count(AgentTaskMemoryAccessTrace.id)).where(
                AgentTaskMemoryAccessTrace.company_id == context.company_id,
                AgentTaskMemoryAccessTrace.owner_agent_id == agent_id,
                AgentTaskMemoryAccessTrace.created_at >= last_24h,
                AgentTaskMemoryAccessTrace.outcome == "cost_limit_denied",
            )
        )
        or 0
    )
    last_30_days = now - timedelta(days=30)
    incident_metrics = (
        await database.execute(
            select(
                func.count(AgentTaskMemoryAccessIncident.id),
                func.coalesce(func.sum(AgentTaskMemoryAccessIncident.revoked_grants), 0),
            ).where(
                AgentTaskMemoryAccessIncident.company_id == context.company_id,
                AgentTaskMemoryAccessIncident.owner_agent_id == agent_id,
                AgentTaskMemoryAccessIncident.created_at >= last_30_days,
            )
        )
    ).one()
    incidents = int(incident_metrics[0])
    incident_revocations = int(incident_metrics[1])
    pending_incident_reviews = int(
        await database.scalar(
            select(func.count(AgentTaskMemoryAccessIncident.id)).where(
                AgentTaskMemoryAccessIncident.company_id == context.company_id,
                AgentTaskMemoryAccessIncident.owner_agent_id == agent_id,
                AgentTaskMemoryAccessIncident.review_status == "pending",
            )
        )
        or 0
    )
    quarantine_until = await database.scalar(
        select(func.max(AgentTaskMemoryAccessIncident.quarantine_until)).where(
            AgentTaskMemoryAccessIncident.company_id == context.company_id,
            AgentTaskMemoryAccessIncident.owner_agent_id == agent_id,
            AgentTaskMemoryAccessIncident.quarantine_until > now,
        )
    )
    quarantined = quarantine_until is not None
    overdue_incident_reviews = int(
        await database.scalar(
            select(func.count(AgentTaskMemoryAccessIncident.id)).where(
                AgentTaskMemoryAccessIncident.company_id == context.company_id,
                AgentTaskMemoryAccessIncident.owner_agent_id == agent_id,
                AgentTaskMemoryAccessIncident.review_status == "pending",
                AgentTaskMemoryAccessIncident.review_due_at <= now,
            )
        )
        or 0
    )
    risk_level: Literal["low", "elevated", "high", "critical"] = "low"
    if quarantined or (incidents and restricted_active_grants):
        risk_level = "critical"
    elif incidents or expired_approvals:
        risk_level = "high"
    elif pending_approvals or blocked_events or cost_denials or restricted_active_grants:
        risk_level = "elevated"
    return AgentMemoryRiskSummary(
        agent_id=agent_id,
        generated_at=now,
        risk_level=risk_level,
        active_grants=active_grants,
        restricted_active_grants=restricted_active_grants,
        pending_approvals=pending_approvals,
        expired_approvals=expired_approvals,
        blocked_events_last_24h=blocked_events,
        cost_denials_last_24h=cost_denials,
        incidents_last_30_days=incidents,
        revoked_grants_last_30_days=incident_revocations,
        pending_incident_reviews=pending_incident_reviews,
        quarantined=quarantined,
        quarantine_until=quarantine_until,
        overdue_incident_reviews=overdue_incident_reviews,
    )


@router.post(
    "/{agent_id}/memory-access-incidents/escalate-overdue",
    response_model=AgentMemoryIncidentEscalationResponse,
)
async def escalate_overdue_agent_memory_incidents(
    agent_id: UUID,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> AgentMemoryIncidentEscalationResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    now = utc_now()
    incidents = list(
        await database.scalars(
            select(AgentTaskMemoryAccessIncident)
            .where(
                AgentTaskMemoryAccessIncident.company_id == context.company_id,
                AgentTaskMemoryAccessIncident.owner_agent_id == agent_id,
                AgentTaskMemoryAccessIncident.review_status == "pending",
                AgentTaskMemoryAccessIncident.review_due_at <= now,
                AgentTaskMemoryAccessIncident.escalated_at.is_(None),
            )
            .with_for_update()
        )
    )
    for incident in incidents:
        incident.escalated_at = now
        incident.escalation_count += 1
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.task_memory_incident.overdue_escalated",
        target_type="agent",
        target_id=agent_id,
        details={"escalated_count": len(incidents)},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.task_memory_incident.overdue_escalated",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="internal",
            payload={"agent_id": str(agent_id), "escalated_count": len(incidents)},
        ),
    )
    await database.commit()
    return AgentMemoryIncidentEscalationResponse(escalated_count=len(incidents), escalated_at=now)


@router.get(
    "/{agent_id}/memory-access-incidents",
    response_model=list[AgentTaskMemoryIncidentResponse],
)
async def list_agent_task_memory_access_incidents(
    agent_id: UUID,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> list[AgentTaskMemoryIncidentResponse]:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    incidents = list(
        await database.scalars(
            select(AgentTaskMemoryAccessIncident)
            .where(
                AgentTaskMemoryAccessIncident.company_id == context.company_id,
                AgentTaskMemoryAccessIncident.owner_agent_id == agent_id,
            )
            .order_by(AgentTaskMemoryAccessIncident.created_at.desc())
            .limit(100)
        )
    )
    return [_task_memory_incident_response(incident) for incident in incidents]


@router.post(
    "/{agent_id}/memory-access-incidents/{incident_id}/review",
    response_model=AgentTaskMemoryIncidentResponse,
)
async def review_agent_task_memory_access_incident(
    agent_id: UUID,
    incident_id: UUID,
    payload: AgentTaskMemoryIncidentReview,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> AgentTaskMemoryIncidentResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    incident = await database.scalar(
        select(AgentTaskMemoryAccessIncident)
        .where(
            AgentTaskMemoryAccessIncident.id == incident_id,
            AgentTaskMemoryAccessIncident.company_id == context.company_id,
            AgentTaskMemoryAccessIncident.owner_agent_id == agent_id,
        )
        .with_for_update()
    )
    if incident is None:
        raise HTTPException(status_code=404, detail="Incidente de memória não encontrado.")
    if incident.review_status != "pending":
        raise HTTPException(status_code=409, detail="O incidente já foi revisado.")
    if incident.triggered_by_user_id == context.user_id:
        raise HTTPException(status_code=409, detail="A revisão exige outra pessoa responsável.")
    existing_review = await database.scalar(
        select(AgentTaskMemoryIncidentReviewRecord.id).where(
            AgentTaskMemoryIncidentReviewRecord.company_id == context.company_id,
            AgentTaskMemoryIncidentReviewRecord.incident_id == incident.id,
            AgentTaskMemoryIncidentReviewRecord.reviewer_user_id == context.user_id,
        )
    )
    if existing_review is not None:
        raise HTTPException(status_code=409, detail="Esta pessoa já revisou o incidente.")
    now = utc_now()
    database.add(
        AgentTaskMemoryIncidentReviewRecord(
            company_id=context.company_id,
            incident_id=incident.id,
            agent_id=agent_id,
            reviewer_user_id=context.user_id,
            decision=payload.decision,
        )
    )
    await database.flush()
    incident.review_count = int(
        await database.scalar(
            select(func.count(AgentTaskMemoryIncidentReviewRecord.id)).where(
                AgentTaskMemoryIncidentReviewRecord.company_id == context.company_id,
                AgentTaskMemoryIncidentReviewRecord.incident_id == incident.id,
            )
        )
        or 0
    )
    decision_count = int(
        await database.scalar(
            select(func.count(AgentTaskMemoryIncidentReviewRecord.id)).where(
                AgentTaskMemoryIncidentReviewRecord.company_id == context.company_id,
                AgentTaskMemoryIncidentReviewRecord.incident_id == incident.id,
                AgentTaskMemoryIncidentReviewRecord.decision == payload.decision,
            )
        )
        or 0
    )
    if decision_count >= incident.required_review_quorum:
        incident.review_status = payload.decision
        incident.reviewed_by_user_id = context.user_id
        incident.reviewed_at = now
        if payload.decision == "dismissed":
            incident.quarantine_until = now
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.task_memory_incident.review_recorded",
        target_type="agent_task_memory_access_incident",
        target_id=incident.id,
        details={
            "agent_id": str(agent_id),
            "decision": payload.decision,
            "review_count": incident.review_count,
            "required_review_quorum": incident.required_review_quorum,
            "final_status": incident.review_status,
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.task_memory_incident.review_recorded",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="confidential",
            payload={
                "incident_id": str(incident.id),
                "agent_id": str(agent_id),
                "review_count": incident.review_count,
                "required_review_quorum": incident.required_review_quorum,
                "final_status": incident.review_status,
            },
        ),
    )
    await database.commit()
    await database.refresh(incident)
    return _task_memory_incident_response(incident)


@router.post(
    "/{agent_id}/memory-risk-report",
    response_model=AgentMemoryRiskReport,
)
async def export_agent_memory_risk_report(
    agent_id: UUID,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
    settings: RequestSettings,
) -> AgentMemoryRiskReport:
    context = get_request_context(principal)
    risk_summary = await get_agent_memory_risk_summary(agent_id, principal, database)
    await database.execute(
        select(Agent.id)
        .where(Agent.id == agent_id, Agent.company_id == context.company_id)
        .with_for_update()
    )
    latest_report = await database.scalar(
        select(AgentMemoryRiskReportRecord)
        .where(
            AgentMemoryRiskReportRecord.company_id == context.company_id,
            AgentMemoryRiskReportRecord.agent_id == agent_id,
        )
        .order_by(AgentMemoryRiskReportRecord.sequence.desc())
        .limit(1)
    )
    signing_key = await database.scalar(
        select(AgentMemoryRiskSigningKeyVersion)
        .where(
            AgentMemoryRiskSigningKeyVersion.company_id == context.company_id,
            AgentMemoryRiskSigningKeyVersion.agent_id == agent_id,
        )
        .order_by(AgentMemoryRiskSigningKeyVersion.version.desc())
        .limit(1)
    )
    if signing_key is None:
        signing_key = AgentMemoryRiskSigningKeyVersion(
            company_id=context.company_id,
            agent_id=agent_id,
            version=1,
            activated_by_user_id=context.user_id,
        )
        database.add(signing_key)
        await database.flush()
    pending_incident_ids = list(
        await database.scalars(
            select(AgentTaskMemoryAccessIncident.id).where(
                AgentTaskMemoryAccessIncident.company_id == context.company_id,
                AgentTaskMemoryAccessIncident.owner_agent_id == agent_id,
                AgentTaskMemoryAccessIncident.review_status == "pending",
            )
        )
    )
    payload = AgentMemoryRiskReportPayload(
        report_id=uuid4(),
        agent_id=agent_id,
        generated_at=utc_now(),
        sequence=(latest_report.sequence + 1 if latest_report else 1),
        previous_signature=(latest_report.signature if latest_report else None),
        signature_key_version=signing_key.version,
        risk_summary=risk_summary,
        pending_incident_ids=pending_incident_ids,
    )
    signature = memory_incident_value_fingerprint(
        secret=settings.encryption_key,
        company_id=context.company_id,
        agent_id=agent_id,
        value_type=f"risk_report_v{payload.signature_key_version}",
        value=_canonical_risk_report(payload),
    )
    database.add(
        AgentMemoryRiskReportRecord(
            id=payload.report_id,
            company_id=context.company_id,
            agent_id=agent_id,
            sequence=payload.sequence,
            signature_key_version=payload.signature_key_version,
            signature=signature,
            previous_signature=payload.previous_signature,
            generated_by_user_id=context.user_id,
        )
    )
    await database.commit()
    return AgentMemoryRiskReport(payload=payload, signature=signature)


@router.post(
    "/{agent_id}/memory-risk-report/verify",
    response_model=AgentMemoryRiskReportVerification,
)
async def verify_agent_memory_risk_report(
    agent_id: UUID,
    payload: AgentMemoryRiskReport,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
    settings: RequestSettings,
) -> AgentMemoryRiskReportVerification:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    if payload.payload.agent_id != agent_id:
        return AgentMemoryRiskReportVerification(valid=False, reason="Relatório de outro agente.")
    record = await database.scalar(
        select(AgentMemoryRiskReportRecord).where(
            AgentMemoryRiskReportRecord.id == payload.payload.report_id,
            AgentMemoryRiskReportRecord.company_id == context.company_id,
            AgentMemoryRiskReportRecord.agent_id == agent_id,
        )
    )
    if record is None:
        return AgentMemoryRiskReportVerification(valid=False, reason="Relatório não registrado.")
    expected = memory_incident_value_fingerprint(
        secret=settings.encryption_key,
        company_id=context.company_id,
        agent_id=agent_id,
        value_type=f"risk_report_v{payload.payload.signature_key_version}",
        value=_canonical_risk_report(payload.payload),
    )
    previous_signature = None
    if payload.payload.sequence > 1:
        previous_signature = await database.scalar(
            select(AgentMemoryRiskReportRecord.signature).where(
                AgentMemoryRiskReportRecord.company_id == context.company_id,
                AgentMemoryRiskReportRecord.agent_id == agent_id,
                AgentMemoryRiskReportRecord.sequence == payload.payload.sequence - 1,
            )
        )
    valid = (
        compare_digest(expected, payload.signature)
        and compare_digest(record.signature, payload.signature)
        and record.sequence == payload.payload.sequence
        and record.signature_key_version == payload.payload.signature_key_version
        and record.previous_signature == payload.payload.previous_signature
        and previous_signature == payload.payload.previous_signature
    )
    return AgentMemoryRiskReportVerification(
        valid=valid,
        reason="Assinatura válida." if valid else "Relatório alterado ou assinatura inválida.",
    )


@router.post(
    "/{agent_id}/memory-risk-signing-keys/rotate",
    response_model=AgentMemoryRiskSigningKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def rotate_agent_memory_risk_signing_key(
    agent_id: UUID,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> AgentMemoryRiskSigningKeyResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    await database.execute(
        select(Agent.id)
        .where(Agent.id == agent_id, Agent.company_id == context.company_id)
        .with_for_update()
    )
    latest_version = int(
        await database.scalar(
            select(func.max(AgentMemoryRiskSigningKeyVersion.version)).where(
                AgentMemoryRiskSigningKeyVersion.company_id == context.company_id,
                AgentMemoryRiskSigningKeyVersion.agent_id == agent_id,
            )
        )
        or 0
    )
    key = AgentMemoryRiskSigningKeyVersion(
        company_id=context.company_id,
        agent_id=agent_id,
        version=latest_version + 1,
        activated_by_user_id=context.user_id,
    )
    database.add(key)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.memory_risk_signing_key.rotated",
        target_type="agent_memory_risk_signing_key_version",
        target_id=key.id,
        details={"agent_id": str(agent_id), "version": key.version},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.memory_risk_signing_key.rotated",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="internal",
            payload={"agent_id": str(agent_id), "version": key.version},
        ),
    )
    await database.commit()
    await database.refresh(key)
    return AgentMemoryRiskSigningKeyResponse(
        id=key.id,
        agent_id=agent_id,
        version=key.version,
        activated_by_user_id=key.activated_by_user_id,
        created_at=key.created_at,
    )


@router.get(
    "/{agent_id}/memory-response-exercises",
    response_model=list[AgentMemoryResponseExerciseResponse],
)
async def list_agent_memory_response_exercises(
    agent_id: UUID,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> list[AgentMemoryResponseExerciseResponse]:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    exercises = list(
        await database.scalars(
            select(AgentMemoryResponseExercise)
            .where(
                AgentMemoryResponseExercise.company_id == context.company_id,
                AgentMemoryResponseExercise.agent_id == agent_id,
            )
            .order_by(AgentMemoryResponseExercise.created_at.desc())
            .limit(50)
        )
    )
    return [
        AgentMemoryResponseExerciseResponse(
            id=exercise.id,
            agent_id=exercise.agent_id,
            scenario=exercise.scenario,
            status=exercise.status,
            checks=exercise.checks,
            requested_by_user_id=exercise.requested_by_user_id,
            created_at=exercise.created_at,
        )
        for exercise in exercises
    ]


@router.post(
    "/{agent_id}/memory-response-exercises",
    response_model=AgentMemoryResponseExerciseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_agent_memory_response_exercise(
    agent_id: UUID,
    payload: AgentMemoryResponseExerciseCreate,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> AgentMemoryResponseExerciseResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    quarantine_violations = int(
        await database.scalar(
            select(func.count(AgentTaskMemoryAccessGrant.id))
            .select_from(AgentTaskMemoryAccessGrant)
            .join(
                AgentTaskMemoryAccessIncident,
                and_(
                    AgentTaskMemoryAccessIncident.company_id
                    == AgentTaskMemoryAccessGrant.company_id,
                    AgentTaskMemoryAccessIncident.owner_agent_id
                    == AgentTaskMemoryAccessGrant.owner_agent_id,
                    AgentTaskMemoryAccessGrant.created_at
                    >= AgentTaskMemoryAccessIncident.created_at,
                    AgentTaskMemoryAccessGrant.created_at
                    < AgentTaskMemoryAccessIncident.quarantine_until,
                ),
            )
            .where(
                AgentTaskMemoryAccessGrant.company_id == context.company_id,
                AgentTaskMemoryAccessGrant.owner_agent_id == agent_id,
                AgentTaskMemoryAccessGrant.status == "active",
            )
        )
        or 0
    )
    quorum_violations = int(
        await database.scalar(
            select(func.count(AgentTaskMemoryAccessIncident.id)).where(
                AgentTaskMemoryAccessIncident.company_id == context.company_id,
                AgentTaskMemoryAccessIncident.owner_agent_id == agent_id,
                AgentTaskMemoryAccessIncident.severity == "critical",
                or_(
                    and_(
                        AgentTaskMemoryAccessIncident.review_status != "pending",
                        AgentTaskMemoryAccessIncident.review_count
                        < AgentTaskMemoryAccessIncident.required_review_quorum,
                    ),
                    and_(
                        AgentTaskMemoryAccessIncident.review_status == "pending",
                        AgentTaskMemoryAccessIncident.review_count
                        >= AgentTaskMemoryAccessIncident.required_review_quorum,
                    ),
                ),
            )
        )
        or 0
    )
    tenant_mismatches = sum(
        int(value or 0)
        for value in (
            await database.scalar(
                select(func.count(AgentTaskMemoryAccessGrant.id)).where(
                    AgentTaskMemoryAccessGrant.owner_agent_id == agent_id,
                    AgentTaskMemoryAccessGrant.company_id != context.company_id,
                )
            ),
            await database.scalar(
                select(func.count(AgentTaskMemoryAccessIncident.id)).where(
                    AgentTaskMemoryAccessIncident.owner_agent_id == agent_id,
                    AgentTaskMemoryAccessIncident.company_id != context.company_id,
                )
            ),
            await database.scalar(
                select(func.count(AgentMemoryRiskReportRecord.id)).where(
                    AgentMemoryRiskReportRecord.agent_id == agent_id,
                    AgentMemoryRiskReportRecord.company_id != context.company_id,
                )
            ),
        )
    )
    report_records = list(
        await database.scalars(
            select(AgentMemoryRiskReportRecord)
            .where(
                AgentMemoryRiskReportRecord.company_id == context.company_id,
                AgentMemoryRiskReportRecord.agent_id == agent_id,
            )
            .order_by(AgentMemoryRiskReportRecord.sequence)
        )
    )
    report_chain_intact = all(
        record.sequence == index + 1
        and record.previous_signature == (report_records[index - 1].signature if index else None)
        for index, record in enumerate(report_records)
    )
    checks = {
        "quarantine_enforced": quarantine_violations == 0,
        "critical_quorum_enforced": quorum_violations == 0,
        "tenant_scope_intact": tenant_mismatches == 0,
        "report_chain_intact": report_chain_intact,
    }
    exercise = AgentMemoryResponseExercise(
        company_id=context.company_id,
        agent_id=agent_id,
        scenario=payload.scenario,
        status="passed" if all(checks.values()) else "failed",
        checks=checks,
        requested_by_user_id=context.user_id,
    )
    database.add(exercise)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.memory_response_exercise.completed",
        target_type="agent_memory_response_exercise",
        target_id=exercise.id,
        details={"status": exercise.status, "checks": checks},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.memory_response_exercise.completed",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="internal",
            payload={"exercise_id": str(exercise.id), "status": exercise.status},
        ),
    )
    await database.commit()
    await database.refresh(exercise)
    return AgentMemoryResponseExerciseResponse(
        id=exercise.id,
        agent_id=agent_id,
        scenario=exercise.scenario,
        status=exercise.status,
        checks=exercise.checks,
        requested_by_user_id=exercise.requested_by_user_id,
        created_at=exercise.created_at,
    )


def _exercise_schedule_response(
    schedule: AgentMemoryExerciseSchedule | None, *, agent_id: UUID
) -> AgentMemoryExerciseScheduleResponse:
    return AgentMemoryExerciseScheduleResponse(
        id=schedule.id if schedule else None,
        agent_id=agent_id,
        enabled=schedule.enabled if schedule else False,
        cadence_hours=schedule.cadence_hours if schedule else 168,
        next_run_at=schedule.next_run_at if schedule else None,
        last_run_at=schedule.last_run_at if schedule else None,
        updated_at=schedule.updated_at if schedule else None,
    )


@router.get(
    "/{agent_id}/memory-response-exercise-schedule",
    response_model=AgentMemoryExerciseScheduleResponse,
)
async def get_agent_memory_exercise_schedule(
    agent_id: UUID,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> AgentMemoryExerciseScheduleResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    schedule = await database.scalar(
        select(AgentMemoryExerciseSchedule).where(
            AgentMemoryExerciseSchedule.company_id == context.company_id,
            AgentMemoryExerciseSchedule.agent_id == agent_id,
        )
    )
    return _exercise_schedule_response(schedule, agent_id=agent_id)


@router.put(
    "/{agent_id}/memory-response-exercise-schedule",
    response_model=AgentMemoryExerciseScheduleResponse,
)
async def update_agent_memory_exercise_schedule(
    agent_id: UUID,
    payload: AgentMemoryExerciseScheduleUpdate,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> AgentMemoryExerciseScheduleResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    schedule = await database.scalar(
        select(AgentMemoryExerciseSchedule)
        .where(
            AgentMemoryExerciseSchedule.company_id == context.company_id,
            AgentMemoryExerciseSchedule.agent_id == agent_id,
        )
        .with_for_update()
    )
    now = utc_now()
    if schedule is None:
        schedule = AgentMemoryExerciseSchedule(
            company_id=context.company_id,
            agent_id=agent_id,
            updated_by_user_id=context.user_id,
        )
        database.add(schedule)
    schedule.enabled = payload.enabled
    schedule.cadence_hours = payload.cadence_hours
    schedule.next_run_at = now + timedelta(hours=payload.cadence_hours) if payload.enabled else None
    schedule.updated_by_user_id = context.user_id
    await database.commit()
    await database.refresh(schedule)
    return _exercise_schedule_response(schedule, agent_id=agent_id)


@router.post(
    "/{agent_id}/memory-response-exercise-schedule/run-due",
    response_model=AgentMemoryExerciseDueResponse,
)
async def run_due_agent_memory_exercise(
    agent_id: UUID,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
) -> AgentMemoryExerciseDueResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    schedule = await database.scalar(
        select(AgentMemoryExerciseSchedule)
        .where(
            AgentMemoryExerciseSchedule.company_id == context.company_id,
            AgentMemoryExerciseSchedule.agent_id == agent_id,
        )
        .with_for_update()
    )
    now = utc_now()
    if (
        schedule is None
        or not schedule.enabled
        or schedule.next_run_at is None
        or schedule.next_run_at > now
    ):
        return AgentMemoryExerciseDueResponse(
            executed=False,
            next_run_at=schedule.next_run_at if schedule else None,
            exercise=None,
        )
    exercise = await run_agent_memory_response_exercise(
        agent_id,
        AgentMemoryResponseExerciseCreate(),
        principal,
        database,
    )
    schedule.last_run_at = now
    schedule.next_run_at = now + timedelta(hours=schedule.cadence_hours)
    schedule.updated_by_user_id = context.user_id
    await database.commit()
    return AgentMemoryExerciseDueResponse(
        executed=True,
        next_run_at=schedule.next_run_at,
        exercise=exercise,
    )


@router.post(
    "/{agent_id}/memory-access-incidents/revoke",
    response_model=AgentTaskMemoryIncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def revoke_agent_task_memory_access_for_incident(
    agent_id: UUID,
    payload: AgentTaskMemoryIncidentRevoke,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
    settings: RequestSettings,
) -> AgentTaskMemoryIncidentResponse:
    context = get_request_context(principal)
    await _tenant_agent(database, company_id=context.company_id, agent_id=agent_id)
    reference_fingerprint = memory_incident_value_fingerprint(
        secret=settings.encryption_key,
        company_id=context.company_id,
        agent_id=agent_id,
        value_type="reference",
        value=payload.incident_reference,
    )
    reason_fingerprint = memory_incident_value_fingerprint(
        secret=settings.encryption_key,
        company_id=context.company_id,
        agent_id=agent_id,
        value_type="reason",
        value=payload.reason,
    )
    existing = await database.scalar(
        select(AgentTaskMemoryAccessIncident).where(
            AgentTaskMemoryAccessIncident.company_id == context.company_id,
            AgentTaskMemoryAccessIncident.idempotency_key == payload.idempotency_key,
        )
    )
    if existing is not None:
        if (
            existing.owner_agent_id != agent_id
            or existing.incident_reference_fingerprint != reference_fingerprint
            or existing.reason_fingerprint != reason_fingerprint
            or existing.quarantine_minutes != payload.quarantine_minutes
            or existing.severity != payload.severity
            or existing.required_review_quorum != payload.required_review_quorum
            or existing.review_sla_minutes != payload.review_sla_minutes
        ):
            raise HTTPException(
                status_code=409, detail="Chave idempotente usada por outro incidente."
            )
        return _task_memory_incident_response(existing, already_processed=True)
    now = utc_now()
    incident = AgentTaskMemoryAccessIncident(
        company_id=context.company_id,
        owner_agent_id=agent_id,
        idempotency_key=payload.idempotency_key,
        incident_reference_fingerprint=reference_fingerprint,
        reason_fingerprint=reason_fingerprint,
        revoked_grants=0,
        quarantine_minutes=payload.quarantine_minutes,
        quarantine_until=now + timedelta(minutes=payload.quarantine_minutes),
        review_status="pending",
        severity=payload.severity,
        required_review_quorum=payload.required_review_quorum,
        review_count=0,
        review_sla_minutes=payload.review_sla_minutes,
        review_due_at=now + timedelta(minutes=payload.review_sla_minutes),
        escalation_count=0,
        triggered_by_user_id=context.user_id,
    )
    database.add(incident)
    await database.flush()
    grants = list(
        await database.scalars(
            select(AgentTaskMemoryAccessGrant)
            .where(
                AgentTaskMemoryAccessGrant.company_id == context.company_id,
                AgentTaskMemoryAccessGrant.owner_agent_id == agent_id,
                AgentTaskMemoryAccessGrant.status == "active",
                AgentTaskMemoryAccessGrant.expires_at > now,
            )
            .with_for_update()
        )
    )
    for grant in grants:
        grant.status = "revoked"
        grant.revoked_by_user_id = context.user_id
        grant.revoked_at = now
        grant.revocation_incident_id = incident.id
        grant.revocation_reason_fingerprint = memory_access_revocation_fingerprint(
            secret=settings.encryption_key,
            company_id=context.company_id,
            grant_id=grant.id,
            reason=payload.reason,
        )
    incident.revoked_grants = len(grants)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="agent.task_memory_access.incident_revoked",
        target_type="agent_task_memory_access_incident",
        target_id=incident.id,
        details={"agent_id": str(agent_id), "revoked_grants": incident.revoked_grants},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="agent.task_memory_access.incident_revoked",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="confidential",
            payload={
                "incident_id": str(incident.id),
                "agent_id": str(agent_id),
                "revoked_grants": incident.revoked_grants,
            },
        ),
    )
    await database.commit()
    await database.refresh(incident)
    return _task_memory_incident_response(incident)


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
    contract = await database.scalar(
        select(AgentTaskContract).where(
            AgentTaskContract.id == delegation.contract_id,
            AgentTaskContract.company_id == context.company_id,
            AgentTaskContract.status == "active",
        )
    )
    if contract is None:
        raise HTTPException(status_code=409, detail="Contrato da tarefa não está ativo.")
    if not set(payload.allowed_tool_keys).issubset(set(contract.allowed_tool_keys)):
        raise HTTPException(
            status_code=422,
            detail="O compartilhamento solicita ferramenta fora do contrato da tarefa.",
        )
    normalized_classifications = sorted(payload.allowed_classifications)
    normalized_tool_keys = sorted(payload.allowed_tool_keys)
    requires_human_approval = payload.max_classification == "restricted"
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
            and sorted(existing.allowed_tool_keys) == normalized_tool_keys
            and existing.max_classification == payload.max_classification
            and existing.max_cost_microunits == payload.max_cost_microunits
            and existing.approval_ttl_minutes
            == (payload.approval_expires_in_minutes if requires_human_approval else None)
            and existing.max_entries == payload.max_entries
            and existing.max_content_characters == payload.max_content_characters
        )
        if not same_contract:
            raise HTTPException(
                status_code=409, detail="Chave idempotente usada por outro contrato."
            )
        return _task_memory_access_response(existing)
    now = utc_now()
    quarantine_id = await database.scalar(
        select(AgentTaskMemoryAccessIncident.id)
        .where(
            AgentTaskMemoryAccessIncident.company_id == context.company_id,
            AgentTaskMemoryAccessIncident.owner_agent_id == agent_id,
            AgentTaskMemoryAccessIncident.quarantine_until > now,
        )
        .limit(1)
    )
    if quarantine_id is not None:
        raise HTTPException(
            status_code=423,
            detail="O agente está em quarentena temporária para revisão de segurança.",
        )
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
        allowed_tool_keys=normalized_tool_keys,
        max_classification=payload.max_classification,
        max_cost_microunits=payload.max_cost_microunits,
        requires_human_approval=requires_human_approval,
        approval_status="pending" if requires_human_approval else "not_required",
        approval_ttl_minutes=(
            payload.approval_expires_in_minutes if requires_human_approval else None
        ),
        approval_expires_at=(
            min(now + timedelta(minutes=payload.approval_expires_in_minutes), expires_at)
            if requires_human_approval
            else None
        ),
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
            "allowed_tool_count": len(grant.allowed_tool_keys),
            "max_classification": grant.max_classification,
            "max_cost_microunits": grant.max_cost_microunits,
            "approval_status": grant.approval_status,
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
    "/{agent_id}/delegations/{delegation_id}/memory-access-grants/{grant_id}/decision",
    response_model=AgentTaskMemoryAccessGrantResponse,
)
async def decide_agent_task_memory_access_grant(
    agent_id: UUID,
    delegation_id: UUID,
    grant_id: UUID,
    payload: AgentTaskMemoryAccessDecision,
    principal: CanConfigureAgentMemory,
    database: DatabaseSession,
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
    now = utc_now()
    if (
        grant.requires_human_approval
        and grant.approval_expires_at is not None
        and grant.approval_expires_at <= now
    ):
        raise HTTPException(status_code=409, detail="A janela de aprovação expirou.")
    if not grant.requires_human_approval or grant.approval_status != "pending":
        raise HTTPException(status_code=409, detail="O contrato não aguarda aprovação.")
    if grant.granted_by_user_id == context.user_id:
        raise HTTPException(status_code=409, detail="A aprovação exige outra pessoa responsável.")
    grant.approval_status = payload.decision
    grant.approved_by_user_id = context.user_id
    grant.approval_decided_at = now
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action=f"agent.task_memory_access.{payload.decision}",
        target_type="agent_task_memory_access_grant",
        target_id=grant.id,
        details={
            "delegation_id": str(delegation_id),
            "max_classification": grant.max_classification,
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=f"agent.task_memory_access.{payload.decision}",
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
            or_(
                AgentTaskMemoryAccessGrant.approval_status == "not_required",
                and_(
                    AgentTaskMemoryAccessGrant.approval_status == "approved",
                    AgentTaskMemoryAccessGrant.approval_expires_at > utc_now(),
                ),
            ),
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
