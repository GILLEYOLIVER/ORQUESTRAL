from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.agents.dispatch_review_service import (
    DispatchReviewError,
    approve_dispatch_retry,
    create_dispatch_review,
)
from app.modules.agents.models import Agent, AgentTool, AgentVersion
from app.modules.agents.review_assignment_service import (
    ReviewAssignmentError,
    acknowledge_review_assignment,
    reassign_review,
)
from app.modules.agents.review_sla_service import dispatch_review_summary
from app.modules.agents.runtime_models import (
    AgentCredentialBinding,
    AgentDispatchReview,
    AgentDispatchReviewAssignment,
    AgentDispatchReviewOnCallException,
    AgentDispatchReviewOnCallHandoff,
    AgentDispatchReviewSLAPolicy,
    AgentEventTrigger,
    AgentExecutionSchedule,
    AgentRuntimeDispatch,
)
from app.modules.agents.runtime_schemas import (
    AgentCredentialBindingCreate,
    AgentCredentialBindingResponse,
    AgentCredentialCatalogResponse,
    AgentDispatchRetryApproval,
    AgentDispatchReviewAssignmentResponse,
    AgentDispatchReviewCreate,
    AgentDispatchReviewOnCallExceptionCreate,
    AgentDispatchReviewOnCallExceptionResponse,
    AgentDispatchReviewOnCallHandoffCreate,
    AgentDispatchReviewOnCallHandoffDecision,
    AgentDispatchReviewOnCallHandoffResponse,
    AgentDispatchReviewReassign,
    AgentDispatchReviewResponse,
    AgentDispatchReviewSLAPolicyCreate,
    AgentDispatchReviewSLAPolicyResponse,
    AgentDispatchReviewSummaryResponse,
    AgentRuntimeDispatchResponse,
    AgentScheduleCreate,
    AgentScheduleResponse,
    AgentTriggerCreate,
    AgentTriggerResponse,
)
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.notifications.service import company_approver_user_ids
from app.modules.plugins.models import IntegrationCredential

router = APIRouter(prefix="/agents", tags=["agents-runtime"])
CanConfigureAgents = Annotated[Principal, Depends(require_permission("agents.configure"))]
CanViewAgents = Annotated[Principal, Depends(require_permission("agents.view"))]
CanExecuteAgents = Annotated[Principal, Depends(require_permission("agents.execute"))]


async def _tenant_agent(database: DatabaseSession, company_id: UUID, agent_id: UUID) -> Agent:
    agent = await database.scalar(
        select(Agent).where(Agent.id == agent_id, Agent.company_id == company_id)
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Agente não encontrado.")
    return agent


async def _tenant_review_sla_policy(
    database: DatabaseSession,
    *,
    company_id: UUID,
    agent_id: UUID,
    policy_id: UUID,
) -> AgentDispatchReviewSLAPolicy:
    policy = await database.scalar(
        select(AgentDispatchReviewSLAPolicy).where(
            AgentDispatchReviewSLAPolicy.id == policy_id,
            AgentDispatchReviewSLAPolicy.company_id == company_id,
            AgentDispatchReviewSLAPolicy.agent_id == agent_id,
        )
    )
    if policy is None:
        raise HTTPException(status_code=404, detail="Política de SLA não encontrada.")
    return policy


async def _active_version(
    database: DatabaseSession, *, company_id: UUID, agent: Agent
) -> AgentVersion:
    if agent.active_version_id is None:
        raise HTTPException(status_code=409, detail="Publique uma versão do agente primeiro.")
    version = await database.scalar(
        select(AgentVersion).where(
            AgentVersion.id == agent.active_version_id,
            AgentVersion.agent_id == agent.id,
            AgentVersion.company_id == company_id,
        )
    )
    if version is None:
        raise HTTPException(status_code=409, detail="A versão ativa do agente não está disponível.")
    return version


def _validated_first_run(value: datetime | None, cadence_minutes: int) -> datetime:
    now = utc_now()
    if value is None:
        return now + timedelta(minutes=cadence_minutes)
    if value <= now:
        raise HTTPException(status_code=422, detail="A primeira execução deve estar no futuro.")
    return value


def _audit_event(
    database: DatabaseSession,
    *,
    company_id: UUID,
    user_id: UUID,
    action: str,
    target_type: str,
    target_id: UUID,
    agent_id: UUID,
) -> None:
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details={"agent_id": str(agent_id)},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=action,
            company_id=company_id,
            actor_user_id=user_id,
            classification="internal",
            payload={"agent_id": str(agent_id), "target_id": str(target_id)},
        ),
    )


@router.get("/{agent_id}/schedules", response_model=list[AgentScheduleResponse])
async def list_agent_schedules(
    agent_id: UUID, principal: CanViewAgents, database: DatabaseSession
) -> list[AgentExecutionSchedule]:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    return list(
        await database.scalars(
            select(AgentExecutionSchedule)
            .where(
                AgentExecutionSchedule.company_id == context.company_id,
                AgentExecutionSchedule.agent_id == agent_id,
            )
            .order_by(
                AgentExecutionSchedule.schedule_key,
                AgentExecutionSchedule.version.desc(),
            )
        )
    )


@router.post(
    "/{agent_id}/schedules",
    response_model=AgentScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_schedule(
    agent_id: UUID,
    payload: AgentScheduleCreate,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentExecutionSchedule:
    context = get_request_context(principal)
    agent = await _tenant_agent(database, context.company_id, agent_id)
    version = await _active_version(database, company_id=context.company_id, agent=agent)
    current = await database.scalar(
        select(func.max(AgentExecutionSchedule.version)).where(
            AgentExecutionSchedule.company_id == context.company_id,
            AgentExecutionSchedule.agent_id == agent_id,
            AgentExecutionSchedule.schedule_key == payload.schedule_key,
        )
    )
    schedule = AgentExecutionSchedule(
        company_id=context.company_id,
        agent_id=agent_id,
        agent_version_id=version.id,
        version=(current or 0) + 1,
        status="draft",
        created_by_user_id=context.user_id,
        next_run_at=_validated_first_run(payload.first_run_at, payload.cadence_minutes),
        **payload.model_dump(exclude={"first_run_at"}),
    )
    database.add(schedule)
    await database.flush()
    _audit_event(
        database,
        company_id=context.company_id,
        user_id=context.user_id,
        action="agent.schedule.created",
        target_type="agent_execution_schedule",
        target_id=schedule.id,
        agent_id=agent_id,
    )
    await database.commit()
    await database.refresh(schedule)
    return schedule


@router.post("/{agent_id}/schedules/{schedule_id}/publish", response_model=AgentScheduleResponse)
async def publish_agent_schedule(
    agent_id: UUID,
    schedule_id: UUID,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentExecutionSchedule:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    schedule = await database.scalar(
        select(AgentExecutionSchedule)
        .where(
            AgentExecutionSchedule.id == schedule_id,
            AgentExecutionSchedule.company_id == context.company_id,
            AgentExecutionSchedule.agent_id == agent_id,
        )
        .with_for_update()
    )
    if schedule is None:
        raise HTTPException(status_code=404, detail="Agenda não encontrada.")
    if schedule.status != "draft":
        raise HTTPException(status_code=409, detail="Somente rascunhos podem ser publicados.")
    await database.execute(
        update(AgentExecutionSchedule)
        .where(
            AgentExecutionSchedule.company_id == context.company_id,
            AgentExecutionSchedule.agent_id == agent_id,
            AgentExecutionSchedule.schedule_key == schedule.schedule_key,
            AgentExecutionSchedule.status.in_(("published", "paused")),
        )
        .values(status="retired")
    )
    schedule.status = "published"
    schedule.published_by_user_id = context.user_id
    schedule.published_at = utc_now()
    _audit_event(
        database,
        company_id=context.company_id,
        user_id=context.user_id,
        action="agent.schedule.published",
        target_type="agent_execution_schedule",
        target_id=schedule.id,
        agent_id=agent_id,
    )
    await database.commit()
    await database.refresh(schedule)
    return schedule


@router.post("/{agent_id}/schedules/{schedule_id}/pause", response_model=AgentScheduleResponse)
async def pause_agent_schedule(
    agent_id: UUID,
    schedule_id: UUID,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentExecutionSchedule:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    schedule = await database.scalar(
        select(AgentExecutionSchedule).where(
            AgentExecutionSchedule.id == schedule_id,
            AgentExecutionSchedule.company_id == context.company_id,
            AgentExecutionSchedule.agent_id == agent_id,
        )
    )
    if schedule is None:
        raise HTTPException(status_code=404, detail="Agenda não encontrada.")
    if schedule.status != "published":
        raise HTTPException(
            status_code=409, detail="Somente agendas publicadas podem ser pausadas."
        )
    schedule.status = "paused"
    _audit_event(
        database,
        company_id=context.company_id,
        user_id=context.user_id,
        action="agent.schedule.paused",
        target_type="agent_execution_schedule",
        target_id=schedule.id,
        agent_id=agent_id,
    )
    await database.commit()
    await database.refresh(schedule)
    return schedule


@router.get("/{agent_id}/event-triggers", response_model=list[AgentTriggerResponse])
async def list_agent_event_triggers(
    agent_id: UUID, principal: CanViewAgents, database: DatabaseSession
) -> list[AgentEventTrigger]:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    return list(
        await database.scalars(
            select(AgentEventTrigger)
            .where(
                AgentEventTrigger.company_id == context.company_id,
                AgentEventTrigger.agent_id == agent_id,
            )
            .order_by(AgentEventTrigger.trigger_key, AgentEventTrigger.version.desc())
        )
    )


@router.post(
    "/{agent_id}/event-triggers",
    response_model=AgentTriggerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_event_trigger(
    agent_id: UUID,
    payload: AgentTriggerCreate,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentEventTrigger:
    context = get_request_context(principal)
    agent = await _tenant_agent(database, context.company_id, agent_id)
    version = await _active_version(database, company_id=context.company_id, agent=agent)
    current = await database.scalar(
        select(func.max(AgentEventTrigger.version)).where(
            AgentEventTrigger.company_id == context.company_id,
            AgentEventTrigger.agent_id == agent_id,
            AgentEventTrigger.trigger_key == payload.trigger_key,
        )
    )
    trigger = AgentEventTrigger(
        company_id=context.company_id,
        agent_id=agent_id,
        agent_version_id=version.id,
        version=(current or 0) + 1,
        status="draft",
        created_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    database.add(trigger)
    await database.flush()
    _audit_event(
        database,
        company_id=context.company_id,
        user_id=context.user_id,
        action="agent.trigger.created",
        target_type="agent_event_trigger",
        target_id=trigger.id,
        agent_id=agent_id,
    )
    await database.commit()
    await database.refresh(trigger)
    return trigger


@router.post(
    "/{agent_id}/event-triggers/{trigger_id}/publish",
    response_model=AgentTriggerResponse,
)
async def publish_agent_event_trigger(
    agent_id: UUID,
    trigger_id: UUID,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentEventTrigger:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    trigger = await database.scalar(
        select(AgentEventTrigger)
        .where(
            AgentEventTrigger.id == trigger_id,
            AgentEventTrigger.company_id == context.company_id,
            AgentEventTrigger.agent_id == agent_id,
        )
        .with_for_update()
    )
    if trigger is None:
        raise HTTPException(status_code=404, detail="Gatilho não encontrado.")
    if trigger.status != "draft":
        raise HTTPException(status_code=409, detail="Somente rascunhos podem ser publicados.")
    await database.execute(
        update(AgentEventTrigger)
        .where(
            AgentEventTrigger.company_id == context.company_id,
            AgentEventTrigger.agent_id == agent_id,
            AgentEventTrigger.trigger_key == trigger.trigger_key,
            AgentEventTrigger.status.in_(("published", "paused")),
        )
        .values(status="retired")
    )
    trigger.status = "published"
    trigger.published_by_user_id = context.user_id
    trigger.published_at = utc_now()
    _audit_event(
        database,
        company_id=context.company_id,
        user_id=context.user_id,
        action="agent.trigger.published",
        target_type="agent_event_trigger",
        target_id=trigger.id,
        agent_id=agent_id,
    )
    await database.commit()
    await database.refresh(trigger)
    return trigger


@router.post(
    "/{agent_id}/event-triggers/{trigger_id}/pause",
    response_model=AgentTriggerResponse,
)
async def pause_agent_event_trigger(
    agent_id: UUID,
    trigger_id: UUID,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentEventTrigger:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    trigger = await database.scalar(
        select(AgentEventTrigger).where(
            AgentEventTrigger.id == trigger_id,
            AgentEventTrigger.company_id == context.company_id,
            AgentEventTrigger.agent_id == agent_id,
        )
    )
    if trigger is None:
        raise HTTPException(status_code=404, detail="Gatilho não encontrado.")
    if trigger.status != "published":
        raise HTTPException(
            status_code=409, detail="Somente gatilhos publicados podem ser pausados."
        )
    trigger.status = "paused"
    _audit_event(
        database,
        company_id=context.company_id,
        user_id=context.user_id,
        action="agent.trigger.paused",
        target_type="agent_event_trigger",
        target_id=trigger.id,
        agent_id=agent_id,
    )
    await database.commit()
    await database.refresh(trigger)
    return trigger


@router.get("/runtime/credential-catalog", response_model=list[AgentCredentialCatalogResponse])
async def list_agent_credential_catalog(
    principal: CanConfigureAgents, database: DatabaseSession
) -> list[AgentCredentialCatalogResponse]:
    context = get_request_context(principal)
    credentials = list(
        await database.scalars(
            select(IntegrationCredential)
            .where(IntegrationCredential.company_id == context.company_id)
            .order_by(IntegrationCredential.name)
        )
    )
    now = utc_now()
    return [
        AgentCredentialCatalogResponse(
            id=item.id,
            plugin_id=item.plugin_id,
            name=item.name,
            status=item.status,
            expires_at=item.expires_at,
            usable=item.status == "active" and (item.expires_at is None or item.expires_at > now),
        )
        for item in credentials
    ]


@router.get(
    "/{agent_id}/credential-bindings",
    response_model=list[AgentCredentialBindingResponse],
)
async def list_agent_credential_bindings(
    agent_id: UUID, principal: CanConfigureAgents, database: DatabaseSession
) -> list[AgentCredentialBinding]:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    return list(
        await database.scalars(
            select(AgentCredentialBinding)
            .where(
                AgentCredentialBinding.company_id == context.company_id,
                AgentCredentialBinding.agent_id == agent_id,
            )
            .order_by(AgentCredentialBinding.tool_key)
        )
    )


@router.put(
    "/{agent_id}/credential-bindings/{tool_key}",
    response_model=AgentCredentialBindingResponse,
)
async def bind_agent_credential(
    agent_id: UUID,
    tool_key: str,
    payload: AgentCredentialBindingCreate,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentCredentialBinding:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    normalized_tool = tool_key.strip().lower()
    tool = await database.scalar(
        select(AgentTool.id).where(
            AgentTool.company_id == context.company_id,
            AgentTool.agent_id == agent_id,
            AgentTool.tool_key == normalized_tool,
            AgentTool.enabled.is_(True),
        )
    )
    if tool is None:
        raise HTTPException(status_code=422, detail="A ferramenta não está habilitada no agente.")
    credential = await database.scalar(
        select(IntegrationCredential).where(
            IntegrationCredential.id == payload.credential_id,
            IntegrationCredential.company_id == context.company_id,
        )
    )
    if credential is None:
        raise HTTPException(status_code=404, detail="Credencial não encontrada.")
    if credential.status != "active" or (
        credential.expires_at is not None and credential.expires_at <= utc_now()
    ):
        raise HTTPException(status_code=409, detail="A credencial não está disponível para uso.")
    binding = await database.scalar(
        select(AgentCredentialBinding).where(
            AgentCredentialBinding.company_id == context.company_id,
            AgentCredentialBinding.agent_id == agent_id,
            AgentCredentialBinding.tool_key == normalized_tool,
        )
    )
    if binding is None:
        binding = AgentCredentialBinding(
            company_id=context.company_id,
            agent_id=agent_id,
            tool_key=normalized_tool,
            credential_id=credential.id,
            enabled=payload.enabled,
            created_by_user_id=context.user_id,
        )
        database.add(binding)
    else:
        binding.credential_id = credential.id
        binding.enabled = payload.enabled
    await database.flush()
    _audit_event(
        database,
        company_id=context.company_id,
        user_id=context.user_id,
        action="agent.credential_binding.updated",
        target_type="agent_credential_binding",
        target_id=binding.id,
        agent_id=agent_id,
    )
    await database.commit()
    await database.refresh(binding)
    return binding


@router.get("/{agent_id}/runtime-dispatches", response_model=list[AgentRuntimeDispatchResponse])
async def list_agent_runtime_dispatches(
    agent_id: UUID, principal: CanViewAgents, database: DatabaseSession
) -> list[AgentRuntimeDispatch]:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    return list(
        await database.scalars(
            select(AgentRuntimeDispatch)
            .where(
                AgentRuntimeDispatch.company_id == context.company_id,
                AgentRuntimeDispatch.agent_id == agent_id,
            )
            .order_by(AgentRuntimeDispatch.created_at.desc())
            .limit(100)
        )
    )


def _raise_review_error(error: DispatchReviewError) -> None:
    status_code = status.HTTP_404_NOT_FOUND if error.code.endswith("not_found") else status.HTTP_409_CONFLICT
    raise HTTPException(status_code=status_code, detail=error.detail) from error


def _raise_assignment_error(error: ReviewAssignmentError) -> None:
    if error.code.endswith("not_found"):
        status_code = status.HTTP_404_NOT_FOUND
    elif error.code.endswith("forbidden"):
        status_code = status.HTTP_403_FORBIDDEN
    elif error.code == "assignee_invalid":
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    else:
        status_code = status.HTTP_409_CONFLICT
    raise HTTPException(status_code=status_code, detail=error.detail) from error


@router.get(
    "/{agent_id}/runtime-dispatch-reviews",
    response_model=list[AgentDispatchReviewResponse],
)
async def list_agent_dispatch_reviews(
    agent_id: UUID, principal: CanViewAgents, database: DatabaseSession
) -> list[AgentDispatchReview]:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    return list(
        await database.scalars(
            select(AgentDispatchReview)
            .where(
                AgentDispatchReview.company_id == context.company_id,
                AgentDispatchReview.agent_id == agent_id,
            )
            .order_by(AgentDispatchReview.created_at.desc())
            .limit(100)
        )
    )


@router.get(
    "/{agent_id}/runtime-dispatch-review-assignments",
    response_model=list[AgentDispatchReviewAssignmentResponse],
)
async def list_agent_dispatch_review_assignments(
    agent_id: UUID, principal: CanViewAgents, database: DatabaseSession
) -> list[AgentDispatchReviewAssignment]:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    return list(
        await database.scalars(
            select(AgentDispatchReviewAssignment)
            .where(
                AgentDispatchReviewAssignment.company_id == context.company_id,
                AgentDispatchReviewAssignment.agent_id == agent_id,
            )
            .order_by(AgentDispatchReviewAssignment.assigned_at.desc())
            .limit(200)
        )
    )


@router.post(
    "/{agent_id}/runtime-dispatch-reviews/{review_id}/assignments/"
    "{assignment_id}/acknowledge",
    response_model=AgentDispatchReviewAssignmentResponse,
)
async def acknowledge_agent_dispatch_review_assignment(
    agent_id: UUID,
    review_id: UUID,
    assignment_id: UUID,
    principal: CanExecuteAgents,
    database: DatabaseSession,
) -> AgentDispatchReviewAssignment:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    try:
        assignment = await acknowledge_review_assignment(
            database,
            company_id=context.company_id,
            agent_id=agent_id,
            review_id=review_id,
            assignment_id=assignment_id,
            actor_user_id=context.user_id,
        )
    except ReviewAssignmentError as error:
        _raise_assignment_error(error)
    await database.commit()
    await database.refresh(assignment)
    return assignment


@router.post(
    "/{agent_id}/runtime-dispatch-reviews/{review_id}/reassign",
    response_model=AgentDispatchReviewAssignmentResponse,
)
async def reassign_agent_dispatch_review(
    agent_id: UUID,
    review_id: UUID,
    payload: AgentDispatchReviewReassign,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentDispatchReviewAssignment:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    try:
        assignment = await reassign_review(
            database,
            company_id=context.company_id,
            agent_id=agent_id,
            review_id=review_id,
            assigned_to_user_id=payload.assigned_to_user_id,
            actor_user_id=context.user_id,
        )
    except ReviewAssignmentError as error:
        _raise_assignment_error(error)
    await database.commit()
    await database.refresh(assignment)
    return assignment


@router.get(
    "/{agent_id}/runtime-dispatch-reviews/summary",
    response_model=AgentDispatchReviewSummaryResponse,
)
async def get_agent_dispatch_review_summary(
    agent_id: UUID,
    principal: CanViewAgents,
    database: DatabaseSession,
    sla_minutes: int | None = None,
) -> AgentDispatchReviewSummaryResponse:
    if sla_minutes is not None and not 5 <= sla_minutes <= 10_080:
        raise HTTPException(status_code=422, detail="O SLA deve ficar entre 5 e 10080 minutos.")
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    summary = await dispatch_review_summary(
        database,
        company_id=context.company_id,
        agent_id=agent_id,
        sla_minutes=sla_minutes,
    )
    return AgentDispatchReviewSummaryResponse.model_validate(asdict(summary))


@router.get(
    "/{agent_id}/runtime-dispatch-review-sla-policies",
    response_model=list[AgentDispatchReviewSLAPolicyResponse],
)
async def list_agent_dispatch_review_sla_policies(
    agent_id: UUID, principal: CanViewAgents, database: DatabaseSession
) -> list[AgentDispatchReviewSLAPolicy]:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    return list(
        await database.scalars(
            select(AgentDispatchReviewSLAPolicy)
            .where(
                AgentDispatchReviewSLAPolicy.company_id == context.company_id,
                AgentDispatchReviewSLAPolicy.agent_id == agent_id,
            )
            .order_by(AgentDispatchReviewSLAPolicy.version.desc())
        )
    )


@router.post(
    "/{agent_id}/runtime-dispatch-review-sla-policies",
    response_model=AgentDispatchReviewSLAPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_dispatch_review_sla_policy(
    agent_id: UUID,
    payload: AgentDispatchReviewSLAPolicyCreate,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentDispatchReviewSLAPolicy:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    requested_on_call_ids = set(payload.on_call_user_ids)
    authorized_on_call_ids = set(
        await company_approver_user_ids(database, context.company_id)
    )
    if not requested_on_call_ids.issubset(authorized_on_call_ids):
        raise HTTPException(
            status_code=422,
            detail="Todos os plantonistas devem ser aprovadores ativos desta empresa.",
        )
    current = await database.scalar(
        select(func.max(AgentDispatchReviewSLAPolicy.version)).where(
            AgentDispatchReviewSLAPolicy.company_id == context.company_id,
            AgentDispatchReviewSLAPolicy.agent_id == agent_id,
        )
    )
    policy = AgentDispatchReviewSLAPolicy(
        company_id=context.company_id,
        agent_id=agent_id,
        version=(current or 0) + 1,
        status="draft",
        created_by_user_id=context.user_id,
        **payload.model_dump(mode="json"),
    )
    database.add(policy)
    await database.flush()
    _audit_event(
        database,
        company_id=context.company_id,
        user_id=context.user_id,
        action="agent.dispatch_review_sla.created",
        target_type="agent_dispatch_review_sla_policy",
        target_id=policy.id,
        agent_id=agent_id,
    )
    await database.commit()
    await database.refresh(policy)
    return policy


@router.post(
    "/{agent_id}/runtime-dispatch-review-sla-policies/{policy_id}/publish",
    response_model=AgentDispatchReviewSLAPolicyResponse,
)
async def publish_agent_dispatch_review_sla_policy(
    agent_id: UUID,
    policy_id: UUID,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentDispatchReviewSLAPolicy:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    policy = await database.scalar(
        select(AgentDispatchReviewSLAPolicy)
        .where(
            AgentDispatchReviewSLAPolicy.id == policy_id,
            AgentDispatchReviewSLAPolicy.company_id == context.company_id,
            AgentDispatchReviewSLAPolicy.agent_id == agent_id,
        )
        .with_for_update()
    )
    if policy is None:
        raise HTTPException(status_code=404, detail="Política de SLA não encontrada.")
    if policy.status != "draft":
        raise HTTPException(status_code=409, detail="Somente rascunhos podem ser publicados.")
    await database.execute(
        update(AgentDispatchReviewSLAPolicy)
        .where(
            AgentDispatchReviewSLAPolicy.company_id == context.company_id,
            AgentDispatchReviewSLAPolicy.agent_id == agent_id,
            AgentDispatchReviewSLAPolicy.status == "published",
        )
        .values(status="retired")
    )
    policy.status = "published"
    policy.published_by_user_id = context.user_id
    policy.published_at = utc_now()
    _audit_event(
        database,
        company_id=context.company_id,
        user_id=context.user_id,
        action="agent.dispatch_review_sla.published",
        target_type="agent_dispatch_review_sla_policy",
        target_id=policy.id,
        agent_id=agent_id,
    )
    await database.commit()
    await database.refresh(policy)
    return policy


@router.get(
    "/{agent_id}/runtime-dispatch-review-sla-policies/{policy_id}/on-call-exceptions",
    response_model=list[AgentDispatchReviewOnCallExceptionResponse],
)
async def list_agent_dispatch_review_on_call_exceptions(
    agent_id: UUID,
    policy_id: UUID,
    principal: CanViewAgents,
    database: DatabaseSession,
) -> list[AgentDispatchReviewOnCallException]:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    await _tenant_review_sla_policy(
        database, company_id=context.company_id, agent_id=agent_id, policy_id=policy_id
    )
    return list(
        await database.scalars(
            select(AgentDispatchReviewOnCallException)
            .where(
                AgentDispatchReviewOnCallException.company_id == context.company_id,
                AgentDispatchReviewOnCallException.agent_id == agent_id,
                AgentDispatchReviewOnCallException.policy_id == policy_id,
            )
            .order_by(AgentDispatchReviewOnCallException.starts_at.desc())
        )
    )


@router.post(
    "/{agent_id}/runtime-dispatch-review-sla-policies/{policy_id}/on-call-exceptions",
    response_model=AgentDispatchReviewOnCallExceptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_dispatch_review_on_call_exception(
    agent_id: UUID,
    policy_id: UUID,
    payload: AgentDispatchReviewOnCallExceptionCreate,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentDispatchReviewOnCallException:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    policy = await _tenant_review_sla_policy(
        database, company_id=context.company_id, agent_id=agent_id, policy_id=policy_id
    )
    if str(payload.user_id) not in policy.on_call_user_ids:
        raise HTTPException(status_code=422, detail="A ausência deve pertencer ao plantão da política.")
    if payload.user_id not in await company_approver_user_ids(database, context.company_id):
        raise HTTPException(status_code=422, detail="O plantonista não é um aprovador ativo.")
    exception = AgentDispatchReviewOnCallException(
        company_id=context.company_id,
        agent_id=agent_id,
        policy_id=policy_id,
        user_id=payload.user_id,
        status="active",
        reason=payload.reason,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        created_by_user_id=context.user_id,
    )
    database.add(exception)
    await database.flush()
    _audit_event(
        database,
        company_id=context.company_id,
        user_id=context.user_id,
        action="agent.dispatch_review.on_call_exception_created",
        target_type="agent_dispatch_review_on_call_exception",
        target_id=exception.id,
        agent_id=agent_id,
    )
    await database.commit()
    await database.refresh(exception)
    return exception


@router.post(
    "/{agent_id}/runtime-dispatch-review-sla-policies/{policy_id}/on-call-exceptions/"
    "{exception_id}/cancel",
    response_model=AgentDispatchReviewOnCallExceptionResponse,
)
async def cancel_agent_dispatch_review_on_call_exception(
    agent_id: UUID,
    policy_id: UUID,
    exception_id: UUID,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentDispatchReviewOnCallException:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    exception = await database.scalar(
        select(AgentDispatchReviewOnCallException)
        .where(
            AgentDispatchReviewOnCallException.id == exception_id,
            AgentDispatchReviewOnCallException.company_id == context.company_id,
            AgentDispatchReviewOnCallException.agent_id == agent_id,
            AgentDispatchReviewOnCallException.policy_id == policy_id,
        )
        .with_for_update()
    )
    if exception is None:
        raise HTTPException(status_code=404, detail="Ausência de plantão não encontrada.")
    if exception.status == "active":
        exception.status = "cancelled"
        _audit_event(
            database,
            company_id=context.company_id,
            user_id=context.user_id,
            action="agent.dispatch_review.on_call_exception_cancelled",
            target_type="agent_dispatch_review_on_call_exception",
            target_id=exception.id,
            agent_id=agent_id,
        )
    await database.commit()
    await database.refresh(exception)
    return exception


@router.get(
    "/{agent_id}/runtime-dispatch-review-sla-policies/{policy_id}/on-call-handoffs",
    response_model=list[AgentDispatchReviewOnCallHandoffResponse],
)
async def list_agent_dispatch_review_on_call_handoffs(
    agent_id: UUID,
    policy_id: UUID,
    principal: CanViewAgents,
    database: DatabaseSession,
) -> list[AgentDispatchReviewOnCallHandoff]:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    await _tenant_review_sla_policy(
        database, company_id=context.company_id, agent_id=agent_id, policy_id=policy_id
    )
    return list(
        await database.scalars(
            select(AgentDispatchReviewOnCallHandoff)
            .where(
                AgentDispatchReviewOnCallHandoff.company_id == context.company_id,
                AgentDispatchReviewOnCallHandoff.agent_id == agent_id,
                AgentDispatchReviewOnCallHandoff.policy_id == policy_id,
            )
            .order_by(AgentDispatchReviewOnCallHandoff.created_at.desc())
        )
    )


@router.post(
    "/{agent_id}/runtime-dispatch-review-sla-policies/{policy_id}/on-call-handoffs",
    response_model=AgentDispatchReviewOnCallHandoffResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_dispatch_review_on_call_handoff(
    agent_id: UUID,
    policy_id: UUID,
    payload: AgentDispatchReviewOnCallHandoffCreate,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentDispatchReviewOnCallHandoff:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    policy = await _tenant_review_sla_policy(
        database, company_id=context.company_id, agent_id=agent_id, policy_id=policy_id
    )
    existing = await database.scalar(
        select(AgentDispatchReviewOnCallHandoff).where(
            AgentDispatchReviewOnCallHandoff.company_id == context.company_id,
            AgentDispatchReviewOnCallHandoff.request_idempotency_key
            == payload.idempotency_key,
        )
    )
    if existing is not None:
        if existing.agent_id != agent_id or existing.policy_id != policy_id:
            raise HTTPException(status_code=409, detail="Chave idempotente já utilizada.")
        return existing
    authorized = set(await company_approver_user_ids(database, context.company_id))
    if (
        str(payload.from_user_id) not in policy.on_call_user_ids
        or payload.from_user_id not in authorized
        or payload.to_user_id not in authorized
    ):
        raise HTTPException(
            status_code=422,
            detail="Origem e substituto devem ser aprovadores ativos desta empresa.",
        )
    handoff = AgentDispatchReviewOnCallHandoff(
        company_id=context.company_id,
        agent_id=agent_id,
        policy_id=policy_id,
        from_user_id=payload.from_user_id,
        to_user_id=payload.to_user_id,
        requested_by_user_id=context.user_id,
        request_idempotency_key=payload.idempotency_key,
        status="pending",
        reason=payload.reason,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
    )
    database.add(handoff)
    await database.flush()
    _audit_event(
        database,
        company_id=context.company_id,
        user_id=context.user_id,
        action="agent.dispatch_review.on_call_handoff_requested",
        target_type="agent_dispatch_review_on_call_handoff",
        target_id=handoff.id,
        agent_id=agent_id,
    )
    await database.commit()
    await database.refresh(handoff)
    return handoff


@router.post(
    "/{agent_id}/runtime-dispatch-review-sla-policies/{policy_id}/on-call-handoffs/"
    "{handoff_id}/respond",
    response_model=AgentDispatchReviewOnCallHandoffResponse,
)
async def respond_agent_dispatch_review_on_call_handoff(
    agent_id: UUID,
    policy_id: UUID,
    handoff_id: UUID,
    payload: AgentDispatchReviewOnCallHandoffDecision,
    principal: CanExecuteAgents,
    database: DatabaseSession,
) -> AgentDispatchReviewOnCallHandoff:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    handoff = await database.scalar(
        select(AgentDispatchReviewOnCallHandoff)
        .where(
            AgentDispatchReviewOnCallHandoff.id == handoff_id,
            AgentDispatchReviewOnCallHandoff.company_id == context.company_id,
            AgentDispatchReviewOnCallHandoff.agent_id == agent_id,
            AgentDispatchReviewOnCallHandoff.policy_id == policy_id,
        )
        .with_for_update()
    )
    if handoff is None:
        raise HTTPException(status_code=404, detail="Passagem de plantão não encontrada.")
    if handoff.to_user_id != context.user_id:
        raise HTTPException(status_code=403, detail="Somente o substituto pode responder.")
    expected_status = "accepted" if payload.decision == "accept" else "rejected"
    if handoff.status == expected_status:
        return handoff
    if handoff.status != "pending":
        raise HTTPException(status_code=409, detail="A passagem já possui decisão final.")
    if handoff.ends_at <= utc_now():
        handoff.status = "expired"
        await database.commit()
        raise HTTPException(status_code=409, detail="A passagem de plantão expirou.")
    handoff.status = expected_status
    handoff.responded_by_user_id = context.user_id
    handoff.responded_at = utc_now()
    _audit_event(
        database,
        company_id=context.company_id,
        user_id=context.user_id,
        action=f"agent.dispatch_review.on_call_handoff_{expected_status}",
        target_type="agent_dispatch_review_on_call_handoff",
        target_id=handoff.id,
        agent_id=agent_id,
    )
    await database.commit()
    await database.refresh(handoff)
    return handoff


@router.post(
    "/{agent_id}/runtime-dispatches/{dispatch_id}/reviews",
    response_model=AgentDispatchReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def review_interrupted_dispatch(
    agent_id: UUID,
    dispatch_id: UUID,
    payload: AgentDispatchReviewCreate,
    principal: CanConfigureAgents,
    database: DatabaseSession,
) -> AgentDispatchReview:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    try:
        review = await create_dispatch_review(
            database,
            company_id=context.company_id,
            agent_id=agent_id,
            dispatch_id=dispatch_id,
            actor_user_id=context.user_id,
            decision=payload.decision,
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
        )
    except DispatchReviewError as error:
        _raise_review_error(error)
    await database.commit()
    await database.refresh(review)
    return review


@router.post(
    "/{agent_id}/runtime-dispatch-reviews/{review_id}/approve-retry",
    response_model=AgentDispatchReviewResponse,
)
async def approve_interrupted_dispatch_retry(
    agent_id: UUID,
    review_id: UUID,
    payload: AgentDispatchRetryApproval,
    principal: CanExecuteAgents,
    database: DatabaseSession,
) -> AgentDispatchReview:
    context = get_request_context(principal)
    await _tenant_agent(database, context.company_id, agent_id)
    try:
        review = await approve_dispatch_retry(
            database,
            company_id=context.company_id,
            agent_id=agent_id,
            review_id=review_id,
            actor_user_id=context.user_id,
            idempotency_key=payload.idempotency_key,
        )
    except DispatchReviewError as error:
        _raise_review_error(error)
    await database.commit()
    await database.refresh(review)
    return review
