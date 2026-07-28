from __future__ import annotations

from datetime import UTC, time, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.marketing.governance_models import MarketingContactPolicy, MarketingDeliveryAttempt
from app.modules.marketing.governance_schemas import (
    MarketingContactPolicyResponse,
    MarketingContactPolicyUpsert,
    MarketingDeliveryDecision,
    MarketingDeliveryOutcome,
    MarketingDeliveryPreflightRequest,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(
    prefix="/marketing/governance",
    tags=["marketing-governance"],
    dependencies=[Depends(require_active_module("marketing"))],
)
CanView = Annotated[Principal, Depends(require_permission("marketing.view"))]
CanManage = Annotated[Principal, Depends(require_permission("marketing.governance.manage"))]
COUNTED_STATUSES = ("reserved", "sent", "delivered")


def _inside_window(value: time, start: time, end: time) -> bool:
    return start <= value <= end if start <= end else value >= start or value <= end


def _policy_response(policy: MarketingContactPolicy) -> MarketingContactPolicyResponse:
    return MarketingContactPolicyResponse.model_validate(policy, from_attributes=True)


@router.get("/policies", response_model=list[MarketingContactPolicyResponse])
async def list_policies(principal: CanView, database: DatabaseSession) -> list[MarketingContactPolicyResponse]:
    context = get_request_context(principal)
    rows = (
        await database.scalars(
            select(MarketingContactPolicy)
            .where(MarketingContactPolicy.company_id == context.company_id)
            .order_by(MarketingContactPolicy.channel)
        )
    ).all()
    return [_policy_response(row) for row in rows]


@router.put("/policies/{channel}", response_model=MarketingContactPolicyResponse)
async def upsert_policy(
    channel: str,
    payload: MarketingContactPolicyUpsert,
    principal: CanManage,
    database: DatabaseSession,
) -> MarketingContactPolicyResponse:
    context = get_request_context(principal)
    if channel != payload.channel:
        raise HTTPException(status_code=422, detail="O canal da rota deve corresponder ao corpo.")
    policy = await database.scalar(
        select(MarketingContactPolicy).where(
            MarketingContactPolicy.company_id == context.company_id,
            MarketingContactPolicy.channel == payload.channel,
        )
    )
    if policy is None:
        policy = MarketingContactPolicy(
            company_id=context.company_id,
            updated_by_user_id=context.user_id,
            **payload.model_dump(),
        )
        database.add(policy)
    else:
        for key, value in payload.model_dump().items():
            setattr(policy, key, value)
        policy.updated_by_user_id = context.user_id
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="marketing.contact_policy.updated",
        target_type="marketing_contact_policy",
        target_id=policy.id,
        details={"channel": policy.channel, "daily_limit": policy.daily_limit, "weekly_limit": policy.weekly_limit},
    )
    await database.commit()
    await database.refresh(policy)
    return _policy_response(policy)


def _decision(attempt: MarketingDeliveryAttempt) -> MarketingDeliveryDecision:
    snapshot = attempt.policy_snapshot
    return MarketingDeliveryDecision(
        attempt_id=attempt.id,
        allowed=attempt.status not in ("blocked", "failed", "cancelled"),
        status=attempt.status,
        reason_code=attempt.reason_code,
        scheduled_for=attempt.scheduled_for,
        daily_count=int(snapshot.get("daily_count", 0)),
        weekly_count=int(snapshot.get("weekly_count", 0)),
    )


@router.post("/preflight", response_model=MarketingDeliveryDecision)
async def preflight_delivery(
    payload: MarketingDeliveryPreflightRequest,
    principal: CanManage,
    database: DatabaseSession,
) -> MarketingDeliveryDecision:
    context = get_request_context(principal)
    existing = await database.scalar(
        select(MarketingDeliveryAttempt).where(
            MarketingDeliveryAttempt.company_id == context.company_id,
            MarketingDeliveryAttempt.idempotency_key == payload.idempotency_key,
        )
    )
    if existing is not None:
        return _decision(existing)
    await database.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"marketing-frequency:{context.company_id}:{payload.contact_id}:{payload.channel}"},
    )
    policy = await database.scalar(
        select(MarketingContactPolicy).where(
            MarketingContactPolicy.company_id == context.company_id,
            MarketingContactPolicy.channel == payload.channel,
            MarketingContactPolicy.enabled.is_(True),
        )
    )
    scheduled_for = payload.scheduled_for or utc_now()
    if scheduled_for.tzinfo is None:
        scheduled_for = scheduled_for.replace(tzinfo=UTC)
    now = utc_now()

    async def count_since(delta: timedelta) -> int:
        return int(
            await database.scalar(
                select(func.count(MarketingDeliveryAttempt.id)).where(
                    MarketingDeliveryAttempt.company_id == context.company_id,
                    MarketingDeliveryAttempt.contact_id == payload.contact_id,
                    MarketingDeliveryAttempt.channel == payload.channel,
                    MarketingDeliveryAttempt.status.in_(COUNTED_STATUSES),
                    MarketingDeliveryAttempt.created_at >= now - delta,
                )
            )
            or 0
        )

    daily_count = await count_since(timedelta(hours=24))
    weekly_count = await count_since(timedelta(days=7))
    reason_code = "allowed"
    if policy is None:
        reason_code = "policy_missing"
    else:
        local = scheduled_for.astimezone(ZoneInfo(policy.timezone))
        if local.weekday() not in policy.allowed_weekdays:
            reason_code = "weekday_blocked"
        elif not _inside_window(local.time().replace(tzinfo=None), policy.window_start, policy.window_end):
            reason_code = "outside_allowed_window"
        elif daily_count >= policy.daily_limit:
            reason_code = "daily_frequency_exceeded"
        elif weekly_count >= policy.weekly_limit:
            reason_code = "weekly_frequency_exceeded"
    if reason_code == "allowed":
        eligibility = (
            await database.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM crm_contacts contact
                        JOIN customer_profile_contacts link
                          ON link.company_id = contact.company_id AND link.contact_id = contact.id
                        WHERE contact.company_id = :company_id AND contact.id = :contact_id
                          AND NOT EXISTS (
                              SELECT 1 FROM customer_processing_restrictions restriction
                              WHERE restriction.company_id = link.company_id
                                AND restriction.profile_id = link.profile_id
                                AND restriction.status = 'active'
                          )
                          AND EXISTS (
                              SELECT 1 FROM customer_consents consent
                              WHERE consent.company_id = link.company_id
                                AND consent.profile_id = link.profile_id
                                AND consent.purpose = 'marketing'
                                AND consent.status = 'granted'
                                AND consent.channel IN ('all', CAST(:channel AS VARCHAR))
                                AND (consent.expires_at IS NULL OR consent.expires_at > :scheduled_for)
                          )
                    ) AS eligible,
                    EXISTS (
                        SELECT 1 FROM crm_contacts
                        WHERE company_id = :company_id AND id = :contact_id
                    ) AS contact_exists
                    """
                ),
                {
                    "company_id": context.company_id,
                    "contact_id": payload.contact_id,
                    "channel": payload.channel,
                    "scheduled_for": scheduled_for,
                },
            )
        ).one()
        if not eligibility.contact_exists:
            raise HTTPException(status_code=404, detail="Contato não encontrado nesta empresa.")
        if not eligibility.eligible:
            reason_code = "consent_or_processing_blocked"
    snapshot = {
        "policy_id": str(policy.id) if policy else None,
        "timezone": policy.timezone if policy else None,
        "daily_limit": policy.daily_limit if policy else None,
        "weekly_limit": policy.weekly_limit if policy else None,
        "daily_count": daily_count,
        "weekly_count": weekly_count,
    }
    attempt = MarketingDeliveryAttempt(
        company_id=context.company_id,
        contact_id=payload.contact_id,
        campaign_id=payload.campaign_id,
        journey_id=payload.journey_id,
        channel=payload.channel,
        status="reserved" if reason_code == "allowed" else "blocked",
        reason_code=reason_code,
        scheduled_for=scheduled_for,
        policy_snapshot=snapshot,
        idempotency_key=payload.idempotency_key,
        created_by_user_id=context.user_id,
    )
    database.add(attempt)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="marketing.delivery.preflight",
        target_type="marketing_delivery_attempt",
        target_id=attempt.id,
        details={"allowed": reason_code == "allowed", "reason_code": reason_code, "channel": payload.channel},
    )
    await database.commit()
    return _decision(attempt)


@router.patch("/attempts/{attempt_id}", response_model=MarketingDeliveryDecision)
async def record_outcome(
    attempt_id: UUID,
    payload: MarketingDeliveryOutcome,
    principal: CanManage,
    database: DatabaseSession,
) -> MarketingDeliveryDecision:
    context = get_request_context(principal)
    attempt = await database.scalar(
        select(MarketingDeliveryAttempt).where(
            MarketingDeliveryAttempt.id == attempt_id,
            MarketingDeliveryAttempt.company_id == context.company_id,
        )
    )
    if attempt is None:
        raise HTTPException(status_code=404, detail="Reserva de envio não encontrada.")
    if attempt.status == "blocked":
        raise HTTPException(status_code=409, detail="Uma tentativa bloqueada não pode ser enviada.")
    attempt.status = payload.status
    attempt.reason_code = payload.reason_code
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="marketing.delivery.outcome_recorded",
        target_type="marketing_delivery_attempt",
        target_id=attempt.id,
        details={"status": attempt.status, "reason_code": attempt.reason_code},
    )
    await database.commit()
    return _decision(attempt)
