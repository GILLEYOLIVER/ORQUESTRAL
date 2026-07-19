from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.security import utc_now
from app.core.tenancy import (
    PlatformAdmin,
    Principal,
    get_request_context,
    require_permission,
)
from app.modules.authorization.service import record_authorization_audit
from app.modules.billing.models import Plan, Subscription, UsageRecord
from app.modules.billing.schemas import (
    BillingOverviewResponse,
    LimitResponse,
    PlanCreate,
    PlanResponse,
    PlanUpdate,
    SubscriptionAssign,
    SubscriptionResponse,
    UsageRecordCreate,
    UsageRecordResponse,
)
from app.modules.billing.service import (
    METRIC_LABELS,
    UsageMetric,
    current_subscription,
    evaluate_limit,
    next_period_end,
    record_usage,
    usage_for_metric,
)
from app.modules.companies.models import Company

router = APIRouter(prefix="/billing", tags=["billing"])
CanViewBilling = Annotated[Principal, Depends(require_permission("billing.view"))]


def plan_response(plan: Plan) -> PlanResponse:
    return PlanResponse.model_validate(plan, from_attributes=True)


def subscription_response(subscription: Subscription, plan: Plan) -> SubscriptionResponse:
    return SubscriptionResponse(
        id=subscription.id,
        company_id=subscription.company_id,
        plan=plan_response(plan),
        status=subscription.status,
        started_at=subscription.started_at,
        trial_ends_at=subscription.trial_ends_at,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancelled_at=subscription.cancelled_at,
    )


def usage_response(record: UsageRecord) -> UsageRecordResponse:
    return UsageRecordResponse(
        id=record.id,
        company_id=record.company_id,
        subscription_id=record.subscription_id,
        metric=record.metric,
        quantity=record.quantity,
        reference_date=record.reference_date,
        metadata=record.record_metadata,
        idempotency_key=record.idempotency_key,
        created_at=record.created_at,
    )


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(principal: CanViewBilling, database: DatabaseSession) -> list[PlanResponse]:
    statement = select(Plan).order_by(Plan.price, Plan.name)
    if not principal.user.is_platform_admin:
        statement = statement.where(Plan.status == "active")
    plans = (await database.scalars(statement)).all()
    return [plan_response(plan) for plan in plans]


@router.post("/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: PlanCreate, principal: PlatformAdmin, database: DatabaseSession
) -> PlanResponse:
    plan = Plan(**payload.model_dump())
    database.add(plan)
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Já existe um plano com esse nome.") from exc
    await database.refresh(plan)
    return plan_response(plan)


@router.patch("/plans/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: UUID,
    payload: PlanUpdate,
    _: PlatformAdmin,
    database: DatabaseSession,
) -> PlanResponse:
    plan = await database.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Já existe um plano com esse nome.") from exc
    await database.refresh(plan)
    return plan_response(plan)


async def _assign_subscription(
    company_id: UUID,
    payload: SubscriptionAssign,
    principal: Principal,
    database: DatabaseSession,
) -> SubscriptionResponse:
    company = await database.get(Company, company_id)
    if company is None or company.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    plan = await database.get(Plan, payload.plan_id)
    if plan is None or plan.status != "active":
        raise HTTPException(status_code=422, detail="Selecione um plano ativo.")
    now = utc_now()
    existing = (
        await database.scalars(
            select(Subscription).where(
                Subscription.company_id == company_id,
                Subscription.status.in_(("trialing", "active", "past_due")),
            )
        )
    ).all()
    for item in existing:
        item.status = "cancelled"
        item.cancelled_at = now
    period_end = (
        payload.trial_ends_at
        if payload.status == "trialing" and payload.trial_ends_at
        else next_period_end(now, plan.billing_cycle)
    )
    subscription = Subscription(
        company_id=company_id,
        plan_id=plan.id,
        status=payload.status,
        started_at=now,
        trial_ends_at=payload.trial_ends_at,
        current_period_start=now,
        current_period_end=period_end,
    )
    database.add(subscription)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=principal.user.id,
        action="billing.subscription.assigned",
        target_type="subscription",
        target_id=subscription.id,
        details={"plan_id": str(plan.id), "status": subscription.status},
    )
    await database.commit()
    await database.refresh(subscription)
    return subscription_response(subscription, plan)


@router.put("/companies/{company_id}/subscription", response_model=SubscriptionResponse)
async def assign_subscription(
    company_id: UUID,
    payload: SubscriptionAssign,
    principal: PlatformAdmin,
    database: DatabaseSession,
) -> SubscriptionResponse:
    return await _assign_subscription(company_id, payload, principal, database)


@router.post("/companies/{company_id}/subscription/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    company_id: UUID, principal: PlatformAdmin, database: DatabaseSession
) -> SubscriptionResponse:
    current = await current_subscription(database, company_id, lock=True)
    if current is None:
        raise HTTPException(status_code=404, detail="Assinatura ativa não encontrada.")
    subscription, plan = current
    subscription.status = "cancelled"
    subscription.cancelled_at = utc_now()
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=principal.user.id,
        action="billing.subscription.cancelled",
        target_type="subscription",
        target_id=subscription.id,
    )
    await database.commit()
    await database.refresh(subscription)
    return subscription_response(subscription, plan)


async def _overview(
    company_id: UUID, database: DatabaseSession, *, enforcement_enabled: bool
) -> BillingOverviewResponse:
    current = await current_subscription(database, company_id)
    if current is None:
        return BillingOverviewResponse(
            enforcement_enabled=enforcement_enabled,
            subscription=None,
            limits=[],
            generated_at=utc_now(),
        )
    subscription, plan = current
    limits: list[LimitResponse] = []
    for metric in UsageMetric:
        used = await usage_for_metric(
            database,
            company_id,
            metric,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
        )
        evaluation = evaluate_limit(
            metric, used=used, configured_limit=plan.limits.get(metric.value)
        )
        limits.append(
            LimitResponse(
                metric=metric.value,
                label=METRIC_LABELS[metric],
                used=evaluation.used,
                limit=evaluation.limit,
                remaining=evaluation.remaining,
                percentage=evaluation.percentage,
                exceeded=evaluation.exceeded,
            )
        )
    return BillingOverviewResponse(
        enforcement_enabled=enforcement_enabled,
        subscription=subscription_response(subscription, plan),
        limits=limits,
        generated_at=utc_now(),
    )


@router.get("/overview", response_model=BillingOverviewResponse)
async def billing_overview(
    principal: CanViewBilling,
    database: DatabaseSession,
    settings: RequestSettings,
) -> BillingOverviewResponse:
    context = get_request_context(principal)
    return await _overview(
        context.company_id,
        database,
        enforcement_enabled=settings.billing_enforcement_enabled,
    )


@router.get("/companies/{company_id}/overview", response_model=BillingOverviewResponse)
async def company_billing_overview(
    company_id: UUID,
    _: PlatformAdmin,
    database: DatabaseSession,
    settings: RequestSettings,
) -> BillingOverviewResponse:
    return await _overview(
        company_id, database, enforcement_enabled=settings.billing_enforcement_enabled
    )


@router.get("/usage-records", response_model=list[UsageRecordResponse])
async def list_usage_records(
    principal: CanViewBilling,
    database: DatabaseSession,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[UsageRecordResponse]:
    context = get_request_context(principal)
    records = (
        await database.scalars(
            select(UsageRecord)
            .where(UsageRecord.company_id == context.company_id)
            .order_by(UsageRecord.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [usage_response(record) for record in records]


@router.post(
    "/companies/{company_id}/usage",
    response_model=UsageRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_external_usage(
    company_id: UUID,
    payload: UsageRecordCreate,
    _: PlatformAdmin,
    database: DatabaseSession,
) -> UsageRecordResponse:
    company = await database.get(Company, company_id)
    if company is None or company.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    record = await record_usage(
        database,
        company_id=company_id,
        metric=UsageMetric(payload.metric),
        quantity=payload.quantity,
        metadata=payload.metadata,
        reference_date=payload.reference_date,
        idempotency_key=payload.idempotency_key,
    )
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Registro de consumo já recebido.") from exc
    await database.refresh(record)
    return usage_response(record)
