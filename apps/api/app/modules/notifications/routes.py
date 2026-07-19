from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.security import utc_now
from app.core.tenancy import CurrentPrincipal, Principal, get_request_context, require_permission
from app.modules.agents.approvals import decide_agent_tool_run
from app.modules.authorization.service import record_authorization_audit
from app.modules.notifications.models import (
    ApprovalAction,
    ApprovalRequest,
    Notification,
    NotificationPreference,
)
from app.modules.notifications.schemas import (
    ApprovalActionResponse,
    ApprovalComment,
    ApprovalDecision,
    ApprovalRequestResponse,
    NotificationMaintenanceResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationResponse,
    NotificationSummaryResponse,
)
from app.modules.notifications.service import (
    process_due_reminders,
    resolve_approval_request,
)
from app.modules.plugins.crypto import CredentialVault, CredentialVaultError
from app.modules.workflows.execution import run_workflow
from app.modules.workflows.models import Workflow, WorkflowExecution

router = APIRouter(prefix="/notifications", tags=["notifications"])
CanViewApprovals = Annotated[Principal, Depends(require_permission("approvals.view"))]
CanDecideApprovals = Annotated[Principal, Depends(require_permission("approvals.decide"))]
CanManageNotifications = Annotated[Principal, Depends(require_permission("notifications.manage"))]


def _notification_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse.model_validate(notification, from_attributes=True)


def _preference_response(
    preference: NotificationPreference,
    settings: RequestSettings,
) -> NotificationPreferenceResponse:
    return NotificationPreferenceResponse(
        event_type=preference.event_type,
        in_app_enabled=preference.in_app_enabled,
        email_enabled=preference.email_enabled,
        whatsapp_enabled=preference.whatsapp_enabled,
        whatsapp_recipient=preference.whatsapp_recipient,
        reminders_enabled=preference.reminders_enabled,
        email_channel_configured=bool(settings.notification_email_webhook_url),
        whatsapp_channel_configured=bool(settings.notification_whatsapp_webhook_url),
    )


def _approval_response(
    approval: ApprovalRequest, actions: list[ApprovalAction]
) -> ApprovalRequestResponse:
    return ApprovalRequestResponse(
        id=approval.id,
        source_type=approval.source_type,
        requested_by_user_id=approval.requested_by_user_id,
        assigned_user_id=approval.assigned_user_id,
        workflow_id=approval.workflow_id,
        workflow_execution_id=approval.workflow_execution_id,
        agent_tool_run_id=approval.agent_tool_run_id,
        title=approval.title,
        description=approval.description,
        context=approval.context,
        status=approval.status,
        reminder_at=approval.reminder_at,
        expires_at=approval.expires_at,
        decided_at=approval.decided_at,
        created_at=approval.created_at,
        actions=[
            ApprovalActionResponse.model_validate(action, from_attributes=True)
            for action in actions
        ],
    )


async def _approval_actions(database: DatabaseSession, approval_id: UUID) -> list[ApprovalAction]:
    return list(
        await database.scalars(
            select(ApprovalAction)
            .where(ApprovalAction.approval_request_id == approval_id)
            .order_by(ApprovalAction.created_at)
        )
    )


@router.get("/summary", response_model=NotificationSummaryResponse)
async def notification_summary(
    principal: CurrentPrincipal, database: DatabaseSession
) -> NotificationSummaryResponse:
    context = get_request_context(principal)
    unread = int(
        await database.scalar(
            select(func.count(Notification.id)).where(
                Notification.company_id == context.company_id,
                Notification.recipient_user_id == context.user_id,
                Notification.channels.contains(["in_app"]),
                Notification.read_at.is_(None),
                Notification.archived_at.is_(None),
            )
        )
        or 0
    )
    pending = 0
    if "approvals.view" in principal.permissions:
        pending = int(
            await database.scalar(
                select(func.count(ApprovalRequest.id)).where(
                    ApprovalRequest.company_id == context.company_id,
                    ApprovalRequest.status == "pending",
                )
            )
            or 0
        )
    return NotificationSummaryResponse(unread_count=unread, pending_approvals=pending)


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    principal: CurrentPrincipal,
    database: DatabaseSession,
    unread_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[NotificationResponse]:
    context = get_request_context(principal)
    statement = select(Notification).where(
        Notification.company_id == context.company_id,
        Notification.recipient_user_id == context.user_id,
        Notification.channels.contains(["in_app"]),
        Notification.archived_at.is_(None),
    )
    if unread_only:
        statement = statement.where(Notification.read_at.is_(None))
    rows = list(
        await database.scalars(statement.order_by(Notification.created_at.desc()).limit(limit))
    )
    return [_notification_response(row) for row in rows]


@router.get("/preferences", response_model=list[NotificationPreferenceResponse])
async def list_preferences(
    principal: CurrentPrincipal,
    database: DatabaseSession,
    settings: RequestSettings,
) -> list[NotificationPreferenceResponse]:
    context = get_request_context(principal)
    rows = list(
        await database.scalars(
            select(NotificationPreference)
            .where(
                NotificationPreference.company_id == context.company_id,
                NotificationPreference.user_id == context.user_id,
            )
            .order_by(NotificationPreference.event_type)
        )
    )
    if not rows:
        preference = NotificationPreference(
            company_id=context.company_id,
            user_id=context.user_id,
            event_type="*",
        )
        database.add(preference)
        await database.commit()
        await database.refresh(preference)
        rows = [preference]
    return [_preference_response(row, settings) for row in rows]


@router.put("/preferences", response_model=NotificationPreferenceResponse)
async def update_preference(
    payload: NotificationPreferenceUpdate,
    principal: CurrentPrincipal,
    database: DatabaseSession,
    settings: RequestSettings,
) -> NotificationPreferenceResponse:
    context = get_request_context(principal)
    preference = await database.scalar(
        select(NotificationPreference).where(
            NotificationPreference.company_id == context.company_id,
            NotificationPreference.user_id == context.user_id,
            NotificationPreference.event_type == payload.event_type,
        )
    )
    if preference is None:
        preference = NotificationPreference(
            company_id=context.company_id,
            user_id=context.user_id,
            event_type=payload.event_type,
        )
        database.add(preference)
    preference.in_app_enabled = payload.in_app_enabled
    preference.email_enabled = payload.email_enabled
    preference.whatsapp_enabled = payload.whatsapp_enabled
    preference.whatsapp_recipient = payload.whatsapp_recipient
    preference.reminders_enabled = payload.reminders_enabled
    await database.commit()
    await database.refresh(preference)
    return _preference_response(preference, settings)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(principal: CurrentPrincipal, database: DatabaseSession) -> None:
    context = get_request_context(principal)
    rows = list(
        await database.scalars(
            select(Notification).where(
                Notification.company_id == context.company_id,
                Notification.recipient_user_id == context.user_id,
                Notification.read_at.is_(None),
            )
        )
    )
    now = utc_now()
    for row in rows:
        row.read_at = now
    await database.commit()


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: UUID,
    principal: CurrentPrincipal,
    database: DatabaseSession,
) -> NotificationResponse:
    context = get_request_context(principal)
    notification = await database.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.company_id == context.company_id,
            Notification.recipient_user_id == context.user_id,
        )
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notificação não encontrada.")
    notification.read_at = notification.read_at or utc_now()
    await database.commit()
    await database.refresh(notification)
    return _notification_response(notification)


@router.get("/approvals", response_model=list[ApprovalRequestResponse])
async def list_approvals(
    principal: CanViewApprovals,
    database: DatabaseSession,
    approval_status: Literal[
        "pending", "approved", "rejected", "cancelled", "expired", "all"
    ] = Query(default="pending", alias="status"),
) -> list[ApprovalRequestResponse]:
    context = get_request_context(principal)
    statement = select(ApprovalRequest).where(ApprovalRequest.company_id == context.company_id)
    if approval_status != "all":
        statement = statement.where(ApprovalRequest.status == approval_status)
    rows = list(
        await database.scalars(statement.order_by(ApprovalRequest.created_at.desc()).limit(200))
    )
    return [_approval_response(row, await _approval_actions(database, row.id)) for row in rows]


@router.post("/approvals/{approval_id}/decision", response_model=ApprovalRequestResponse)
async def decide_approval(
    approval_id: UUID,
    payload: ApprovalDecision,
    principal: CanDecideApprovals,
    database: DatabaseSession,
    settings: RequestSettings,
) -> ApprovalRequestResponse:
    context = get_request_context(principal)
    approval = await database.scalar(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.company_id == context.company_id,
        )
        .with_for_update()
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="Solicitação de aprovação não encontrada.")
    if approval.assigned_user_id is not None and approval.assigned_user_id != context.user_id:
        raise HTTPException(status_code=403, detail="Esta decisão foi atribuída a outro usuário.")
    if approval.expires_at is not None and approval.expires_at <= utc_now():
        raise HTTPException(status_code=409, detail="Esta solicitação de aprovação expirou.")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail="Esta solicitação já recebeu uma decisão.")

    if approval.agent_tool_run_id is not None:
        await decide_agent_tool_run(
            database,
            run_id=approval.agent_tool_run_id,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            permissions=principal.permissions,
            decision=payload.decision,
            settings=settings,
            sync_approval=False,
        )
    await resolve_approval_request(
        database,
        approval=approval,
        actor_user_id=context.user_id,
        decision=payload.decision,
        comment=payload.comment,
    )

    if approval.workflow_execution_id is not None:
        execution = await database.scalar(
            select(WorkflowExecution).where(
                WorkflowExecution.id == approval.workflow_execution_id,
                WorkflowExecution.company_id == context.company_id,
            )
        )
        if execution is None:
            raise HTTPException(status_code=404, detail="Execução vinculada não encontrada.")
        if payload.decision == "rejected":
            execution.status = "canceled"
            execution.error_summary = "Execução rejeitada por decisão humana."
            execution.finished_at = utc_now()
        else:
            workflow = await database.scalar(
                select(Workflow).where(
                    Workflow.id == execution.workflow_id,
                    Workflow.company_id == context.company_id,
                )
            )
            if workflow is None or approval.encrypted_payload is None:
                raise HTTPException(status_code=409, detail="Automação vinculada indisponível.")
            try:
                encrypted = CredentialVault(settings.encryption_key).decrypt(
                    approval.encrypted_payload
                )
            except CredentialVaultError as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            input_data = encrypted.get("input", {})
            if not isinstance(input_data, dict):
                raise HTTPException(status_code=500, detail="Payload de retomada inválido.")
            await run_workflow(
                workflow,
                input_data,
                database,
                settings,
                source=execution.source,
                requested_by_user_id=execution.requested_by_user_id,
                existing_execution=execution,
                bypass_approval=True,
            )

    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action=f"approval.{payload.decision}",
        target_type="approval_request",
        target_id=approval.id,
        details={"source_type": approval.source_type},
    )
    await database.commit()
    await database.refresh(approval)
    return _approval_response(approval, await _approval_actions(database, approval.id))


@router.post("/approvals/{approval_id}/comments", response_model=ApprovalRequestResponse)
async def comment_approval(
    approval_id: UUID,
    payload: ApprovalComment,
    principal: CanViewApprovals,
    database: DatabaseSession,
) -> ApprovalRequestResponse:
    context = get_request_context(principal)
    approval = await database.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.company_id == context.company_id,
        )
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="Solicitação de aprovação não encontrada.")
    database.add(
        ApprovalAction(
            company_id=context.company_id,
            approval_request_id=approval.id,
            actor_user_id=context.user_id,
            action="commented",
            comment=payload.comment,
        )
    )
    await database.commit()
    return _approval_response(approval, await _approval_actions(database, approval.id))


@router.post("/maintenance", response_model=NotificationMaintenanceResponse)
async def run_maintenance(
    principal: CanManageNotifications,
    database: DatabaseSession,
    settings: RequestSettings,
) -> NotificationMaintenanceResponse:
    get_request_context(principal)
    reminders = await process_due_reminders(
        database, reminder_minutes=settings.notification_reminder_minutes
    )
    await database.commit()
    return NotificationMaintenanceResponse(reminders_created=reminders)
