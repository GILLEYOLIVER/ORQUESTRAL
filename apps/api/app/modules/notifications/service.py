from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import timedelta
from typing import Any, Literal
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import create_database_engine, create_session_factory
from app.core.security import utc_now
from app.modules.authorization.models import Permission, RolePermission
from app.modules.notifications.models import (
    ApprovalAction,
    ApprovalRequest,
    Notification,
    NotificationPreference,
)
from app.modules.users.models import CompanyUser, User
from app.modules.workflows.models import WorkflowExecution

Decision = Literal["approved", "rejected"]


def channels_for_preference(preference: NotificationPreference | None) -> list[str]:
    if preference is None:
        return ["in_app"]
    channels: list[str] = []
    if preference.in_app_enabled:
        channels.append("in_app")
    if preference.email_enabled:
        channels.append("email")
    if preference.whatsapp_enabled and preference.whatsapp_recipient:
        channels.append("whatsapp")
    return channels


async def get_notification_preference(
    database: AsyncSession,
    *,
    company_id: UUID,
    user_id: UUID,
    event_type: str,
) -> NotificationPreference | None:
    exact = await database.scalar(
        select(NotificationPreference).where(
            NotificationPreference.company_id == company_id,
            NotificationPreference.user_id == user_id,
            NotificationPreference.event_type == event_type,
        )
    )
    if exact is not None:
        return exact
    fallback: NotificationPreference | None = await database.scalar(
        select(NotificationPreference).where(
            NotificationPreference.company_id == company_id,
            NotificationPreference.user_id == user_id,
            NotificationPreference.event_type == "*",
        )
    )
    return fallback


async def create_notification(
    database: AsyncSession,
    *,
    company_id: UUID,
    recipient_user_id: UUID,
    event_type: str,
    title: str,
    message: str,
    severity: str = "info",
    resource_type: str | None = None,
    resource_id: UUID | str | None = None,
    data: dict[str, Any] | None = None,
) -> Notification | None:
    preference = await get_notification_preference(
        database,
        company_id=company_id,
        user_id=recipient_user_id,
        event_type=event_type,
    )
    channels = channels_for_preference(preference)
    if not channels:
        return None
    delivery_status = {
        channel: {"state": "delivered" if channel == "in_app" else "pending", "attempts": 0}
        for channel in channels
    }
    notification = Notification(
        company_id=company_id,
        recipient_user_id=recipient_user_id,
        event_type=event_type,
        title=title,
        message=message,
        severity=severity,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        data=dict(data or {}),
        channels=channels,
        delivery_status=delivery_status,
    )
    database.add(notification)
    await database.flush()
    return notification


async def company_approver_user_ids(database: AsyncSession, company_id: UUID) -> list[UUID]:
    owner_ids = set(
        await database.scalars(
            select(CompanyUser.user_id).where(
                CompanyUser.company_id == company_id,
                CompanyUser.status == "active",
                CompanyUser.is_owner.is_(True),
            )
        )
    )
    permission_role_ids = set(
        await database.scalars(
            select(RolePermission.role_id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(Permission.code == "approvals.decide")
        )
    )
    if permission_role_ids:
        owner_ids.update(
            await database.scalars(
                select(CompanyUser.user_id).where(
                    CompanyUser.company_id == company_id,
                    CompanyUser.status == "active",
                    CompanyUser.role_id.in_(permission_role_ids),
                )
            )
        )
    return sorted(owner_ids, key=str)


async def is_company_approver(database: AsyncSession, *, company_id: UUID, user_id: UUID) -> bool:
    return user_id in await company_approver_user_ids(database, company_id)


async def create_approval_request(
    database: AsyncSession,
    *,
    company_id: UUID,
    requested_by_user_id: UUID | None,
    source_type: str,
    title: str,
    description: str,
    context: dict[str, Any] | None = None,
    assigned_user_id: UUID | None = None,
    recipient_user_ids: Sequence[UUID] | None = None,
    required_permission: str = "approvals.decide",
    workflow_id: UUID | None = None,
    workflow_execution_id: UUID | None = None,
    agent_tool_run_id: UUID | None = None,
    encrypted_payload: bytes | None = None,
    expires_at: Any | None = None,
    reminder_minutes: int = 30,
) -> ApprovalRequest:
    approval = ApprovalRequest(
        company_id=company_id,
        requested_by_user_id=requested_by_user_id,
        assigned_user_id=assigned_user_id,
        workflow_id=workflow_id,
        workflow_execution_id=workflow_execution_id,
        agent_tool_run_id=agent_tool_run_id,
        source_type=source_type,
        required_permission=required_permission,
        title=title,
        description=description,
        context=dict(context or {}),
        encrypted_payload=encrypted_payload,
        reminder_at=utc_now() + timedelta(minutes=reminder_minutes),
        expires_at=expires_at,
    )
    database.add(approval)
    await database.flush()
    recipients = (
        list(recipient_user_ids)
        if recipient_user_ids is not None
        else [assigned_user_id]
        if assigned_user_id
        else await company_approver_user_ids(database, company_id)
    )
    if not recipients and requested_by_user_id is not None:
        recipients = [requested_by_user_id]
    for recipient_id in dict.fromkeys(recipient for recipient in recipients if recipient):
        await create_notification(
            database,
            company_id=company_id,
            recipient_user_id=recipient_id,
            event_type="approval.requested",
            title="Decisão necessária",
            message=title,
            severity="warning",
            resource_type="approval_request",
            resource_id=approval.id,
            data={"source_type": source_type},
        )
    return approval


async def resolve_approval_request(
    database: AsyncSession,
    *,
    approval: ApprovalRequest,
    actor_user_id: UUID,
    decision: Decision,
    comment: str | None = None,
) -> None:
    if approval.status != "pending":
        raise ValueError("Esta solicitação já recebeu uma decisão.")
    approval.status = decision
    approval.decided_at = utc_now()
    database.add(
        ApprovalAction(
            company_id=approval.company_id,
            approval_request_id=approval.id,
            actor_user_id=actor_user_id,
            action=decision,
            comment=comment,
        )
    )
    if approval.requested_by_user_id is not None:
        await create_notification(
            database,
            company_id=approval.company_id,
            recipient_user_id=approval.requested_by_user_id,
            event_type=f"approval.{decision}",
            title="Solicitação aprovada" if decision == "approved" else "Solicitação rejeitada",
            message=approval.title,
            severity="success" if decision == "approved" else "error",
            resource_type="approval_request",
            resource_id=approval.id,
        )


async def resolve_linked_agent_approval(
    database: AsyncSession,
    *,
    company_id: UUID,
    agent_tool_run_id: UUID,
    actor_user_id: UUID,
    decision: Decision,
    comment: str | None = None,
) -> None:
    approval = await database.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.company_id == company_id,
            ApprovalRequest.agent_tool_run_id == agent_tool_run_id,
            ApprovalRequest.status == "pending",
        )
    )
    if approval is not None:
        await resolve_approval_request(
            database,
            approval=approval,
            actor_user_id=actor_user_id,
            decision=decision,
            comment=comment,
        )


async def process_due_reminders(database: AsyncSession, *, reminder_minutes: int) -> int:
    now = utc_now()
    approvals = list(
        await database.scalars(
            select(ApprovalRequest)
            .where(
                ApprovalRequest.status == "pending",
                ApprovalRequest.reminder_at.is_not(None),
                ApprovalRequest.reminder_at <= now,
            )
            .order_by(ApprovalRequest.reminder_at)
            .limit(200)
        )
    )
    created = 0
    for approval in approvals:
        if approval.expires_at is not None and approval.expires_at <= now:
            approval.status = "expired"
            approval.decided_at = now
            database.add(
                ApprovalAction(
                    company_id=approval.company_id,
                    approval_request_id=approval.id,
                    action="expired",
                )
            )
            if approval.workflow_execution_id is not None:
                execution = await database.get(WorkflowExecution, approval.workflow_execution_id)
                if execution is not None and execution.status == "waiting":
                    execution.status = "canceled"
                    execution.error_summary = "A solicitação de aprovação expirou."
                    execution.finished_at = now
            continue
        recipients = (
            [approval.assigned_user_id]
            if approval.assigned_user_id
            else await company_approver_user_ids(database, approval.company_id)
        )
        for recipient_id in recipients:
            preference = await get_notification_preference(
                database,
                company_id=approval.company_id,
                user_id=recipient_id,
                event_type="approval.reminder",
            )
            if preference is not None and not preference.reminders_enabled:
                continue
            notification = await create_notification(
                database,
                company_id=approval.company_id,
                recipient_user_id=recipient_id,
                event_type="approval.reminder",
                title="Aprovação ainda pendente",
                message=approval.title,
                severity="warning",
                resource_type="approval_request",
                resource_id=approval.id,
            )
            if notification is not None:
                created += 1
        database.add(
            ApprovalAction(
                company_id=approval.company_id,
                approval_request_id=approval.id,
                action="reminded",
            )
        )
        approval.reminder_at = now + timedelta(minutes=reminder_minutes)
    await database.flush()
    return created


async def deliver_pending_notifications(database: AsyncSession, settings: Settings) -> int:
    notifications = list(
        await database.scalars(
            select(Notification).order_by(Notification.created_at.desc()).limit(500)
        )
    )
    delivered = 0
    async with httpx.AsyncClient(timeout=settings.notification_delivery_timeout_seconds) as client:
        for notification in notifications:
            statuses = dict(notification.delivery_status)
            pending_channels = [
                channel
                for channel in ("email", "whatsapp")
                if statuses.get(channel, {}).get("state") in {"pending", "failed"}
                and int(statuses.get(channel, {}).get("attempts", 0)) < 3
                and (channel != "email" or settings.email_delivery_enabled)
            ]
            if not pending_channels:
                continue
            user = await database.get(User, notification.recipient_user_id)
            preference = await get_notification_preference(
                database,
                company_id=notification.company_id,
                user_id=notification.recipient_user_id,
                event_type=notification.event_type,
            )
            for channel in pending_channels:
                current = dict(statuses.get(channel, {}))
                current["attempts"] = int(current.get("attempts", 0)) + 1
                endpoint = (
                    settings.notification_email_webhook_url
                    if channel == "email"
                    else settings.notification_whatsapp_webhook_url
                )
                recipient = (
                    user.email
                    if channel == "email" and user is not None
                    else preference.whatsapp_recipient
                    if preference is not None
                    else None
                )
                if not endpoint or not recipient:
                    current["state"] = "not_configured"
                    statuses[channel] = current
                    continue
                payload = {
                    "notification_id": str(notification.id),
                    "company_id": str(notification.company_id),
                    "channel": channel,
                    "recipient": recipient,
                    "event_type": notification.event_type,
                    "title": notification.title,
                    "message": notification.message,
                    "data": notification.data,
                }
                try:
                    response = await client.post(str(endpoint), json=payload)
                    response.raise_for_status()
                    current["state"] = "delivered"
                    current["delivered_at"] = utc_now().isoformat()
                    current.pop("error", None)
                    delivered += 1
                except httpx.HTTPError as exc:
                    current["state"] = "failed"
                    current["error"] = str(exc)[:300]
                statuses[channel] = current
            notification.delivery_status = statuses
    await database.flush()
    return delivered


async def run_notification_maintenance() -> dict[str, int]:
    settings = get_settings()
    engine = create_database_engine(str(settings.database_url))
    sessions = create_session_factory(engine)
    try:
        async with sessions() as database:
            reminders = await process_due_reminders(
                database, reminder_minutes=settings.notification_reminder_minutes
            )
            deliveries = await deliver_pending_notifications(database, settings)
            await database.commit()
            return {"reminders": reminders, "deliveries": deliveries}
    finally:
        await engine.dispose()


def run_notification_maintenance_sync() -> dict[str, int]:
    return asyncio.run(run_notification_maintenance())
