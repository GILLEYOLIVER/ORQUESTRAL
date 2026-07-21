from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.crm.models import CRMContact, CRMOpportunity
from app.modules.marketing.models import (
    MarketingAttribution,
    MarketingCampaign,
    MarketingCampaignContact,
    MarketingCampaignMetric,
    MarketingExperiment,
)
from app.modules.marketing.schemas import (
    AttributionCreate,
    AttributionResponse,
    CampaignMetricCreate,
    CampaignMetricResponse,
    CampaignPerformanceResponse,
    ExperimentCreate,
    ExperimentResponse,
    ExperimentUpdate,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(prefix="/marketing", tags=["marketing-growth"])

ActiveMarketing = Annotated[Principal, Depends(require_active_module("marketing"))]
CanViewMarketing = Annotated[Principal, Depends(require_permission("marketing.view"))]
CanCreateMarketing = Annotated[Principal, Depends(require_permission("marketing.create"))]
CanUpdateMarketing = Annotated[Principal, Depends(require_permission("marketing.update"))]


async def _campaign(
    database: DatabaseSession, company_id: UUID, campaign_id: UUID
) -> MarketingCampaign:
    campaign = await database.scalar(
        select(MarketingCampaign).where(
            MarketingCampaign.id == campaign_id,
            MarketingCampaign.company_id == company_id,
            MarketingCampaign.archived_at.is_(None),
        )
    )
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")
    return campaign


def _metric_response(metric: MarketingCampaignMetric) -> CampaignMetricResponse:
    return CampaignMetricResponse.model_validate(metric, from_attributes=True)


def _experiment_response(experiment: MarketingExperiment) -> ExperimentResponse:
    return ExperimentResponse.model_validate(experiment, from_attributes=True)


def _attribution_response(attribution: MarketingAttribution) -> AttributionResponse:
    return AttributionResponse.model_validate(attribution, from_attributes=True)


def _performance(
    campaign_id: UUID | None, metrics: list[MarketingCampaignMetric]
) -> CampaignPerformanceResponse:
    impressions = sum(item.impressions for item in metrics)
    reach = sum(item.reach for item in metrics)
    clicks = sum(item.clicks for item in metrics)
    leads = sum(item.leads for item in metrics)
    conversions = sum(item.conversions for item in metrics)
    spend = sum(item.spend_cents for item in metrics)
    revenue = sum(item.revenue_cents for item in metrics)
    return CampaignPerformanceResponse(
        campaign_id=campaign_id,
        impressions=impressions,
        reach=reach,
        clicks=clicks,
        leads=leads,
        conversions=conversions,
        spend_cents=spend,
        revenue_cents=revenue,
        click_rate=round((clicks / impressions * 100) if impressions else 0, 2),
        lead_rate=round((leads / clicks * 100) if clicks else 0, 2),
        conversion_rate=round((conversions / leads * 100) if leads else 0, 2),
        cost_per_lead_cents=round(spend / leads) if leads else 0,
        acquisition_cost_cents=round(spend / conversions) if conversions else 0,
        roas=round((revenue / spend) if spend else 0, 2),
    )


@router.get("/performance", response_model=CampaignPerformanceResponse)
async def overall_performance(
    principal: CanViewMarketing,
    _: ActiveMarketing,
    database: DatabaseSession,
) -> CampaignPerformanceResponse:
    context = get_request_context(principal)
    metrics = list(
        await database.scalars(
            select(MarketingCampaignMetric).where(
                MarketingCampaignMetric.company_id == context.company_id
            )
        )
    )
    return _performance(None, metrics)


@router.get(
    "/campaigns/{campaign_id}/performance",
    response_model=CampaignPerformanceResponse,
)
async def campaign_performance(
    campaign_id: UUID,
    principal: CanViewMarketing,
    _: ActiveMarketing,
    database: DatabaseSession,
) -> CampaignPerformanceResponse:
    context = get_request_context(principal)
    await _campaign(database, context.company_id, campaign_id)
    metrics = list(
        await database.scalars(
            select(MarketingCampaignMetric).where(
                MarketingCampaignMetric.company_id == context.company_id,
                MarketingCampaignMetric.campaign_id == campaign_id,
            )
        )
    )
    return _performance(campaign_id, metrics)


@router.get(
    "/campaigns/{campaign_id}/metrics",
    response_model=list[CampaignMetricResponse],
)
async def list_campaign_metrics(
    campaign_id: UUID,
    principal: CanViewMarketing,
    _: ActiveMarketing,
    database: DatabaseSession,
) -> list[CampaignMetricResponse]:
    context = get_request_context(principal)
    await _campaign(database, context.company_id, campaign_id)
    metrics = list(
        await database.scalars(
            select(MarketingCampaignMetric)
            .where(
                MarketingCampaignMetric.company_id == context.company_id,
                MarketingCampaignMetric.campaign_id == campaign_id,
            )
            .order_by(MarketingCampaignMetric.observed_on.desc())
        )
    )
    return [_metric_response(metric) for metric in metrics]


@router.post(
    "/campaigns/{campaign_id}/metrics",
    response_model=CampaignMetricResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_campaign_metric(
    campaign_id: UUID,
    payload: CampaignMetricCreate,
    principal: CanUpdateMarketing,
    _: ActiveMarketing,
    database: DatabaseSession,
) -> CampaignMetricResponse:
    context = get_request_context(principal)
    campaign = await _campaign(database, context.company_id, campaign_id)
    metric = await database.scalar(
        select(MarketingCampaignMetric).where(
            MarketingCampaignMetric.campaign_id == campaign_id,
            MarketingCampaignMetric.observed_on == payload.observed_on,
            MarketingCampaignMetric.channel == payload.channel,
            MarketingCampaignMetric.variant_key == payload.variant_key,
        )
    )
    if metric is None:
        metric = MarketingCampaignMetric(
            company_id=context.company_id,
            campaign_id=campaign_id,
            **payload.model_dump(),
        )
        database.add(metric)
    else:
        for field, value in payload.model_dump().items():
            setattr(metric, field, value)
    await database.flush()
    total_spend = await database.scalar(
        select(func.coalesce(func.sum(MarketingCampaignMetric.spend_cents), 0)).where(
            MarketingCampaignMetric.campaign_id == campaign_id
        )
    )
    campaign.spent_cents = int(total_spend or 0)
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Esta métrica já foi registrada.") from exc
    await database.refresh(metric)
    return _metric_response(metric)


@router.get("/experiments", response_model=list[ExperimentResponse])
async def list_experiments(
    principal: CanViewMarketing,
    _: ActiveMarketing,
    database: DatabaseSession,
    campaign_id: Annotated[UUID | None, Query()] = None,
) -> list[ExperimentResponse]:
    context = get_request_context(principal)
    query = select(MarketingExperiment).where(MarketingExperiment.company_id == context.company_id)
    if campaign_id is not None:
        query = query.where(MarketingExperiment.campaign_id == campaign_id)
    items = list(await database.scalars(query.order_by(MarketingExperiment.created_at.desc())))
    return [_experiment_response(item) for item in items]


@router.post("/experiments", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    payload: ExperimentCreate,
    principal: CanCreateMarketing,
    _: ActiveMarketing,
    database: DatabaseSession,
) -> ExperimentResponse:
    context = get_request_context(principal)
    await _campaign(database, context.company_id, payload.campaign_id)
    keys = [str(item.get("key", "")).strip() for item in payload.variants]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise HTTPException(status_code=422, detail="Cada variante deve possuir uma chave única.")
    experiment = MarketingExperiment(
        company_id=context.company_id,
        status="draft",
        **payload.model_dump(),
    )
    database.add(experiment)
    await database.commit()
    await database.refresh(experiment)
    return _experiment_response(experiment)


@router.patch("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    experiment_id: UUID,
    payload: ExperimentUpdate,
    principal: CanUpdateMarketing,
    _: ActiveMarketing,
    database: DatabaseSession,
) -> ExperimentResponse:
    context = get_request_context(principal)
    experiment = await database.scalar(
        select(MarketingExperiment).where(
            MarketingExperiment.id == experiment_id,
            MarketingExperiment.company_id == context.company_id,
        )
    )
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experimento não encontrado.")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("winner_key") is not None:
        keys = {str(item.get("key")) for item in experiment.variants}
        if changes["winner_key"] not in keys:
            raise HTTPException(status_code=422, detail="A variante vencedora é inválida.")
    if changes.get("status") == "running" and experiment.start_at is None:
        changes.setdefault("start_at", utc_now())
    if changes.get("status") == "completed":
        changes.setdefault("end_at", utc_now())
    for field, value in changes.items():
        setattr(experiment, field, value)
    await database.commit()
    await database.refresh(experiment)
    return _experiment_response(experiment)


@router.get(
    "/campaigns/{campaign_id}/attributions",
    response_model=list[AttributionResponse],
)
async def list_attributions(
    campaign_id: UUID,
    principal: CanViewMarketing,
    _: ActiveMarketing,
    database: DatabaseSession,
) -> list[AttributionResponse]:
    context = get_request_context(principal)
    await _campaign(database, context.company_id, campaign_id)
    items = list(
        await database.scalars(
            select(MarketingAttribution)
            .where(
                MarketingAttribution.company_id == context.company_id,
                MarketingAttribution.campaign_id == campaign_id,
            )
            .order_by(MarketingAttribution.occurred_at.desc())
        )
    )
    return [_attribution_response(item) for item in items]


@router.post(
    "/campaigns/{campaign_id}/attributions",
    response_model=AttributionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_attribution(
    campaign_id: UUID,
    payload: AttributionCreate,
    principal: CanUpdateMarketing,
    _: ActiveMarketing,
    database: DatabaseSession,
) -> AttributionResponse:
    context = get_request_context(principal)
    await _campaign(database, context.company_id, campaign_id)
    if payload.contact_id is not None:
        contact = await database.scalar(
            select(CRMContact.id).where(
                CRMContact.id == payload.contact_id,
                CRMContact.company_id == context.company_id,
                CRMContact.deleted_at.is_(None),
            )
        )
        if contact is None:
            raise HTTPException(status_code=422, detail="Contato inválido para esta empresa.")
    if payload.opportunity_id is not None:
        opportunity = await database.scalar(
            select(CRMOpportunity.id).where(
                CRMOpportunity.id == payload.opportunity_id,
                CRMOpportunity.company_id == context.company_id,
                CRMOpportunity.deleted_at.is_(None),
            )
        )
        if opportunity is None:
            raise HTTPException(status_code=422, detail="Oportunidade inválida para esta empresa.")
    attribution = MarketingAttribution(
        company_id=context.company_id,
        campaign_id=campaign_id,
        contact_id=payload.contact_id,
        opportunity_id=payload.opportunity_id,
        touchpoint=payload.touchpoint,
        source=payload.source,
        medium=payload.medium,
        value_cents=payload.value_cents,
        metadata_json=payload.metadata_json,
        occurred_at=payload.occurred_at or utc_now(),
    )
    database.add(attribution)
    if payload.contact_id is not None and payload.touchpoint == "conversion":
        audience = await database.scalar(
            select(MarketingCampaignContact).where(
                MarketingCampaignContact.campaign_id == campaign_id,
                MarketingCampaignContact.contact_id == payload.contact_id,
            )
        )
        if audience is not None:
            audience.status = "converted"
            audience.last_interaction_at = attribution.occurred_at
    await database.commit()
    await database.refresh(attribution)
    return _attribution_response(attribution)
