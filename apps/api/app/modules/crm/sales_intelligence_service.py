from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.sales_intelligence_schemas import (
    ForecastCategory,
    HealthLevel,
    OpportunityInsightResponse,
    SalesForecastResponse,
)

MONEY = Decimal("0.01")


@dataclass(frozen=True)
class OpportunitySignal:
    opportunity_id: UUID
    title: str
    amount: Decimal
    probability: int
    expected_close_date: date | None
    assigned_user_id: UUID | None
    created_at: datetime
    last_activity_at: datetime | None
    activity_count: int
    has_proposal: bool
    has_published_quote: bool
    has_accepted_quote: bool


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _next_action(
    signal: OpportunitySignal,
    *,
    today: date,
    stale_days: int,
) -> str:
    if signal.has_accepted_quote:
        return "Atualizar a etapa e preparar o fechamento do negócio."
    if signal.expected_close_date is not None and signal.expected_close_date < today:
        return "Revisar a data prevista e confirmar se o negócio continua ativo."
    if signal.activity_count == 0:
        return "Registrar o primeiro contato e combinar um próximo passo."
    if stale_days > 14:
        return "Retomar o contato e registrar um compromisso com data definida."
    if not signal.has_published_quote and signal.probability >= 40:
        return "Preparar e publicar uma proposta comercial."
    if signal.assigned_user_id is None:
        return "Definir uma pessoa responsável pela oportunidade."
    return "Confirmar o próximo passo com o cliente e registrar a atividade."


def evaluate_opportunity(
    signal: OpportunitySignal,
    *,
    today: date | None = None,
) -> OpportunityInsightResponse:
    evaluation_date = today or datetime.now(UTC).date()
    reference_date = (signal.last_activity_at or signal.created_at).date()
    stale_days = max((evaluation_date - reference_date).days, 0)
    score = 30 + round(signal.probability * 0.4)
    reasons: list[str] = []

    if signal.activity_count == 0:
        score -= 20
        reasons.append("Ainda não existe atividade comercial registrada.")
    elif stale_days <= 7:
        score += 15
        reasons.append("Existe atividade comercial nos últimos sete dias.")
    elif stale_days <= 14:
        score += 7
        reasons.append("A última atividade ocorreu há até quatorze dias.")
    elif stale_days <= 30:
        score -= 8
        reasons.append("A oportunidade está sem atividade há mais de quatorze dias.")
    else:
        score -= 20
        reasons.append("A oportunidade está sem atividade há mais de trinta dias.")

    if signal.expected_close_date is None:
        score -= 5
        reasons.append("A data prevista de fechamento não foi informada.")
    elif signal.expected_close_date < evaluation_date:
        score -= 20
        reasons.append("A data prevista de fechamento está vencida.")
    elif (signal.expected_close_date - evaluation_date).days <= 14:
        reasons.append("O fechamento está previsto para os próximos quatorze dias.")

    if signal.has_accepted_quote:
        score += 20
        reasons.append("Existe uma proposta aceita.")
    elif signal.has_published_quote:
        score += 10
        reasons.append("Existe uma proposta publicada aguardando decisão.")
    elif signal.has_proposal:
        score += 3
        reasons.append("Existe uma proposta em preparação.")
    elif signal.probability >= 40:
        reasons.append("Ainda não existe proposta comercial publicada.")

    if signal.amount <= 0:
        score -= 10
        reasons.append("O valor estimado não foi informado.")
    if signal.assigned_user_id is None:
        score -= 10
        reasons.append("A oportunidade não possui responsável definido.")

    health_score = max(0, min(score, 100))
    if health_score >= 70:
        health_level: HealthLevel = "healthy"
    elif health_score >= 45:
        health_level = "attention"
    else:
        health_level = "critical"

    if signal.has_accepted_quote or (
        signal.probability >= 70 and health_score >= 65
    ):
        forecast_category: ForecastCategory = "commit"
    elif signal.probability >= 40 and health_score >= 40:
        forecast_category = "best_case"
    else:
        forecast_category = "pipeline"

    weighted_amount = _money(
        signal.amount * Decimal(signal.probability) / Decimal(100)
    )
    return OpportunityInsightResponse(
        opportunity_id=signal.opportunity_id,
        title=signal.title,
        amount=_money(signal.amount),
        probability=signal.probability,
        weighted_amount=weighted_amount,
        expected_close_date=signal.expected_close_date,
        last_activity_at=signal.last_activity_at,
        stale_days=stale_days,
        activity_count=signal.activity_count,
        health_score=health_score,
        health_level=health_level,
        forecast_category=forecast_category,
        has_proposal=signal.has_proposal,
        has_published_quote=signal.has_published_quote,
        has_accepted_quote=signal.has_accepted_quote,
        reasons=reasons,
        next_best_action=_next_action(
            signal,
            today=evaluation_date,
            stale_days=stale_days,
        ),
    )


async def list_opportunity_insights(
    database: AsyncSession,
    *,
    company_id: UUID,
    limit: int = 100,
) -> list[OpportunityInsightResponse]:
    rows = (
        await database.execute(
            text(
                """
                SELECT
                    opportunity.id,
                    opportunity.title,
                    opportunity.amount,
                    COALESCE(opportunity.probability, stage.probability, 0) AS probability,
                    opportunity.expected_close_date,
                    opportunity.assigned_user_id,
                    opportunity.created_at,
                    MAX(activity.occurred_at) AS last_activity_at,
                    COUNT(DISTINCT activity.id) AS activity_count,
                    COALESCE(BOOL_OR(quote.id IS NOT NULL), FALSE) AS has_proposal,
                    COALESCE(BOOL_OR(quote.status = 'published'), FALSE)
                        AS has_published_quote,
                    COALESCE(BOOL_OR(quote.status = 'accepted'), FALSE)
                        AS has_accepted_quote
                FROM crm_opportunities AS opportunity
                JOIN crm_pipeline_stages AS stage
                  ON stage.id = opportunity.stage_id
                 AND stage.company_id = :company_id
                LEFT JOIN crm_opportunity_activities AS activity
                  ON activity.opportunity_id = opportunity.id
                 AND activity.company_id = :company_id
                LEFT JOIN crm_quotes AS quote
                  ON quote.opportunity_id = opportunity.id
                 AND quote.company_id = :company_id
                WHERE opportunity.company_id = :company_id
                  AND opportunity.deleted_at IS NULL
                  AND opportunity.status = 'open'
                GROUP BY
                    opportunity.id,
                    opportunity.title,
                    opportunity.amount,
                    opportunity.probability,
                    stage.probability,
                    opportunity.expected_close_date,
                    opportunity.assigned_user_id,
                    opportunity.created_at,
                    opportunity.updated_at
                ORDER BY opportunity.updated_at DESC, opportunity.id
                LIMIT :limit
                """
            ),
            {"company_id": company_id, "limit": limit},
        )
    ).mappings()
    return [
        evaluate_opportunity(
            OpportunitySignal(
                opportunity_id=row["id"],
                title=row["title"],
                amount=Decimal(row["amount"]),
                probability=int(row["probability"]),
                expected_close_date=row["expected_close_date"],
                assigned_user_id=row["assigned_user_id"],
                created_at=row["created_at"],
                last_activity_at=row["last_activity_at"],
                activity_count=int(row["activity_count"]),
                has_proposal=bool(row["has_proposal"]),
                has_published_quote=bool(row["has_published_quote"]),
                has_accepted_quote=bool(row["has_accepted_quote"]),
            )
        )
        for row in rows
    ]


async def build_sales_forecast(
    database: AsyncSession,
    *,
    company_id: UUID,
    limit: int = 100,
) -> SalesForecastResponse:
    opportunities = await list_opportunity_insights(
        database,
        company_id=company_id,
        limit=limit,
    )
    total_open = sum((item.amount for item in opportunities), Decimal(0))
    weighted = sum((item.weighted_amount for item in opportunities), Decimal(0))
    pipeline = sum(
        (
            item.amount
            for item in opportunities
            if item.forecast_category == "pipeline"
        ),
        Decimal(0),
    )
    best_case = sum(
        (
            item.amount
            for item in opportunities
            if item.forecast_category == "best_case"
        ),
        Decimal(0),
    )
    commit = sum(
        (
            item.amount
            for item in opportunities
            if item.forecast_category == "commit"
        ),
        Decimal(0),
    )
    today = datetime.now(UTC).date()
    return SalesForecastResponse(
        generated_at=datetime.now(UTC),
        currency="BRL",
        opportunity_count=len(opportunities),
        at_risk_count=sum(
            item.health_level != "healthy" for item in opportunities
        ),
        overdue_count=sum(
            item.expected_close_date is not None
            and item.expected_close_date < today
            for item in opportunities
        ),
        total_open_amount=_money(total_open),
        weighted_amount=_money(weighted),
        pipeline_amount=_money(pipeline),
        best_case_amount=_money(best_case),
        commit_amount=_money(commit),
        opportunities=opportunities,
    )
