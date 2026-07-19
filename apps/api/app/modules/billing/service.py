from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utc_now
from app.modules.agents.models import Agent, AgentUsageRecord
from app.modules.billing.models import Plan, Subscription, UsageRecord
from app.modules.knowledge.models import KnowledgeDocument
from app.modules.plugins.models import CompanyPlugin
from app.modules.users.models import CompanyUser
from app.modules.workflows.models import Workflow, WorkflowExecution


class UsageMetric(StrEnum):
    USERS = "users"
    AGENTS = "agents"
    WORKFLOWS = "workflows"
    WORKFLOW_EXECUTIONS = "workflow_executions"
    TOKENS = "tokens"
    STORAGE_BYTES = "storage_bytes"
    INTEGRATIONS = "integrations"
    DOCUMENTS = "documents"
    API_CALLS = "api_calls"


METRIC_LABELS: dict[UsageMetric, str] = {
    UsageMetric.USERS: "Usuários",
    UsageMetric.AGENTS: "Agentes",
    UsageMetric.WORKFLOWS: "Automações",
    UsageMetric.WORKFLOW_EXECUTIONS: "Execuções no período",
    UsageMetric.TOKENS: "Tokens no período",
    UsageMetric.STORAGE_BYTES: "Armazenamento",
    UsageMetric.INTEGRATIONS: "Integrações",
    UsageMetric.DOCUMENTS: "Documentos",
    UsageMetric.API_CALLS: "Chamadas de API no período",
}


@dataclass(frozen=True, slots=True)
class LimitEvaluation:
    metric: UsageMetric
    used: int
    limit: int | None
    remaining: int | None
    percentage: float | None
    exceeded: bool


def next_period_end(start: datetime, billing_cycle: str) -> datetime:
    if billing_cycle == "yearly":
        try:
            return start.replace(year=start.year + 1)
        except ValueError:
            return start.replace(year=start.year + 1, day=28)
    if billing_cycle != "monthly":
        raise ValueError(f"Ciclo de cobrança inválido: {billing_cycle}")
    month = 1 if start.month == 12 else start.month + 1
    year = start.year + 1 if start.month == 12 else start.year
    day = min(start.day, monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


def evaluate_limit(
    metric: UsageMetric, *, used: int, increment: int = 0, configured_limit: int | None
) -> LimitEvaluation:
    projected = used + increment
    remaining = None if configured_limit is None else max(0, configured_limit - used)
    percentage = (
        None if configured_limit is None else round(min(100.0, (used / configured_limit) * 100), 2)
    )
    return LimitEvaluation(
        metric=metric,
        used=used,
        limit=configured_limit,
        remaining=remaining,
        percentage=percentage,
        exceeded=configured_limit is not None and projected > configured_limit,
    )


def assert_capacity(evaluation: LimitEvaluation) -> None:
    if not evaluation.exceeded:
        return
    label = METRIC_LABELS[evaluation.metric]
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail=(
            f"O limite de {label.lower()} do plano foi atingido. "
            "Ajuste o plano ou reduza o consumo para continuar."
        ),
    )


async def current_subscription(
    database: AsyncSession, company_id: UUID, *, lock: bool = False
) -> tuple[Subscription, Plan] | None:
    statement = (
        select(Subscription, Plan)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(
            Subscription.company_id == company_id,
            Subscription.status.in_(("trialing", "active", "past_due")),
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    if lock:
        statement = statement.with_for_update()
    row = (await database.execute(statement)).one_or_none()
    if row is None:
        return None
    subscription, plan = row[0], row[1]
    now = utc_now()
    if subscription.status == "trialing" and subscription.trial_ends_at:
        if subscription.trial_ends_at <= now:
            subscription.status = "expired"
            return None
    if subscription.status == "active" and subscription.current_period_end <= now:
        while subscription.current_period_end <= now:
            subscription.current_period_start = subscription.current_period_end
            subscription.current_period_end = next_period_end(
                subscription.current_period_start, plan.billing_cycle
            )
    return subscription, plan


async def usage_for_metric(
    database: AsyncSession,
    company_id: UUID,
    metric: UsageMetric,
    *,
    period_start: datetime,
    period_end: datetime,
) -> int:
    if metric is UsageMetric.USERS:
        statement = select(func.count(CompanyUser.id)).where(
            CompanyUser.company_id == company_id,
            CompanyUser.status.in_(("active", "invited")),
        )
    elif metric is UsageMetric.AGENTS:
        statement = select(func.count(Agent.id)).where(
            Agent.company_id == company_id, Agent.status == "active"
        )
    elif metric is UsageMetric.WORKFLOWS:
        statement = select(func.count(Workflow.id)).where(Workflow.company_id == company_id)
    elif metric is UsageMetric.WORKFLOW_EXECUTIONS:
        statement = select(func.count(WorkflowExecution.id)).where(
            WorkflowExecution.company_id == company_id,
            WorkflowExecution.created_at >= period_start,
            WorkflowExecution.created_at < period_end,
        )
    elif metric is UsageMetric.TOKENS:
        statement = select(func.coalesce(func.sum(AgentUsageRecord.total_tokens), 0)).where(
            AgentUsageRecord.company_id == company_id,
            AgentUsageRecord.created_at >= period_start,
            AgentUsageRecord.created_at < period_end,
        )
    elif metric is UsageMetric.STORAGE_BYTES:
        statement = select(func.coalesce(func.sum(KnowledgeDocument.size_bytes), 0)).where(
            KnowledgeDocument.company_id == company_id
        )
    elif metric is UsageMetric.INTEGRATIONS:
        statement = select(func.count(CompanyPlugin.id)).where(
            CompanyPlugin.company_id == company_id, CompanyPlugin.status == "active"
        )
    elif metric is UsageMetric.DOCUMENTS:
        statement = select(func.count(KnowledgeDocument.id)).where(
            KnowledgeDocument.company_id == company_id
        )
    else:
        statement = select(func.coalesce(func.sum(UsageRecord.quantity), 0)).where(
            UsageRecord.company_id == company_id,
            UsageRecord.metric == metric.value,
            UsageRecord.reference_date >= period_start.date(),
            UsageRecord.reference_date < period_end.date(),
        )
    value = await database.scalar(statement)
    return int(value or 0)


async def enforce_limit(
    database: AsyncSession,
    *,
    company_id: UUID,
    metric: UsageMetric,
    increment: int = 1,
    enforcement_enabled: bool,
) -> LimitEvaluation:
    if increment < 1:
        raise ValueError("O incremento de consumo deve ser positivo")
    current = await current_subscription(database, company_id, lock=enforcement_enabled)
    if current is None:
        if enforcement_enabled:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="A empresa precisa de uma assinatura ativa para continuar.",
            )
        return evaluate_limit(metric, used=0, increment=increment, configured_limit=None)
    subscription, plan = current
    used = await usage_for_metric(
        database,
        company_id,
        metric,
        period_start=subscription.current_period_start,
        period_end=subscription.current_period_end,
    )
    evaluation = evaluate_limit(
        metric,
        used=used,
        increment=increment,
        configured_limit=plan.limits.get(metric.value),
    )
    if enforcement_enabled:
        assert_capacity(evaluation)
    return evaluation


async def record_usage(
    database: AsyncSession,
    *,
    company_id: UUID,
    metric: UsageMetric,
    quantity: int,
    metadata: dict[str, Any] | None = None,
    reference_date: date | None = None,
    idempotency_key: str | None = None,
) -> UsageRecord:
    current = await current_subscription(database, company_id)
    record = UsageRecord(
        company_id=company_id,
        subscription_id=current[0].id if current else None,
        metric=metric.value,
        quantity=quantity,
        reference_date=reference_date or datetime.now(UTC).date(),
        record_metadata=metadata or {},
        idempotency_key=idempotency_key,
    )
    database.add(record)
    return record
