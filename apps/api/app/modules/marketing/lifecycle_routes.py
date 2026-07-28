from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.agents.models import Agent, AgentVersion
from app.modules.authorization.service import record_authorization_audit
from app.modules.marketing.content_models import MarketingContent
from app.modules.marketing.lifecycle_models import (
    MarketingAgentRecommendation,
    MarketingExperimentEvidence,
    MarketingJourneySimulation,
    MarketingJourneyVersion,
)
from app.modules.marketing.lifecycle_schemas import (
    ExperimentEvidenceCreate,
    ExperimentEvidenceResponse,
    JourneySimulationRequest,
    JourneySimulationResponse,
    JourneyVersionResponse,
    MarketingAgentRecommendationCreate,
    MarketingAgentRecommendationDecision,
    MarketingAgentRecommendationResponse,
)
from app.modules.marketing.models import (
    MarketingCampaign,
    MarketingCampaignMetric,
    MarketingExperiment,
    MarketingJourney,
    MarketingJourneyStep,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(
    prefix="/marketing/lifecycle",
    tags=["marketing-lifecycle"],
    dependencies=[Depends(require_active_module("marketing"))],
)
CanView = Annotated[Principal, Depends(require_permission("marketing.view"))]
CanManageJourneys = Annotated[Principal, Depends(require_permission("marketing.journeys.manage"))]
CanManageGrowth = Annotated[Principal, Depends(require_permission("marketing.update"))]
CanManageAgents = Annotated[Principal, Depends(require_permission("marketing.agents.manage"))]


async def _journey_definition(
    database: DatabaseSession, *, company_id: UUID, journey_id: UUID
) -> tuple[MarketingJourney, dict[str, Any]]:
    journey = await database.scalar(
        select(MarketingJourney).where(
            MarketingJourney.id == journey_id,
            MarketingJourney.company_id == company_id,
            MarketingJourney.archived_at.is_(None),
        )
    )
    if journey is None:
        raise HTTPException(status_code=404, detail="Jornada não encontrada.")
    steps = (
        await database.scalars(
            select(MarketingJourneyStep)
            .where(
                MarketingJourneyStep.company_id == company_id,
                MarketingJourneyStep.journey_id == journey_id,
            )
            .order_by(MarketingJourneyStep.position)
        )
    ).all()
    definition = {
        "name": journey.name,
        "description": journey.description,
        "trigger_type": journey.trigger_type,
        "steps": [
            {
                "id": str(step.id),
                "name": step.name,
                "action_type": step.action_type,
                "position": step.position,
                "configuration": step.configuration,
            }
            for step in steps
        ],
    }
    return journey, definition


def _validate_journey(definition: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    steps = definition["steps"]
    if not steps:
        issues.append({"code": "journey_without_steps", "message": "Adicione ao menos uma etapa."})
    positions = [step["position"] for step in steps]
    if positions != list(range(len(positions))):
        issues.append({"code": "non_contiguous_positions", "message": "As posições devem ser contínuas."})
    for step in steps:
        if step["action_type"] == "webhook":
            issues.append(
                {
                    "code": "unsupported_external_effect",
                    "step_id": step["id"],
                    "message": "Webhook exige um adaptador governado antes da publicação.",
                }
            )
        if step["action_type"] in {"email", "whatsapp", "sms"} and not step["configuration"].get("content_id"):
            issues.append(
                {
                    "code": "content_required",
                    "step_id": step["id"],
                    "message": "Etapa de comunicação exige conteúdo aprovado.",
                }
            )
    return issues


def _definition_checksum(definition: dict[str, Any]) -> str:
    encoded = json.dumps(definition, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


async def _content_issues(
    database: DatabaseSession, *, company_id: UUID, definition: dict[str, Any]
) -> list[dict[str, Any]]:
    expected: dict[UUID, tuple[str, str]] = {}
    issues: list[dict[str, Any]] = []
    for step in definition["steps"]:
        if step["action_type"] not in {"email", "whatsapp", "sms"}:
            continue
        raw_content_id = step["configuration"].get("content_id")
        if not raw_content_id:
            continue
        try:
            expected[UUID(str(raw_content_id))] = (step["id"], step["action_type"])
        except ValueError:
            issues.append(
                {
                    "code": "invalid_content_id",
                    "step_id": step["id"],
                    "message": "O identificador do conteúdo é inválido.",
                }
            )
    if not expected:
        return issues
    rows = (
        await database.scalars(
            select(MarketingContent).where(
                MarketingContent.company_id == company_id,
                MarketingContent.id.in_(expected),
                MarketingContent.status == "approved",
            )
        )
    ).all()
    approved = {row.id: row for row in rows}
    for content_id, (step_id, action_type) in expected.items():
        content = approved.get(content_id)
        if content is None or content.kind != action_type:
            issues.append(
                {
                    "code": "approved_content_required",
                    "step_id": step_id,
                    "message": "Use conteúdo aprovado e compatível com o canal.",
                }
            )
    return issues


@router.post(
    "/journeys/{journey_id}/simulate",
    response_model=JourneySimulationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def simulate_journey(
    journey_id: UUID,
    payload: JourneySimulationRequest,
    principal: CanManageJourneys,
    database: DatabaseSession,
) -> JourneySimulationResponse:
    context = get_request_context(principal)
    _, definition = await _journey_definition(
        database, company_id=context.company_id, journey_id=journey_id
    )
    issues = _validate_journey(definition)
    issues.extend(
        await _content_issues(database, company_id=context.company_id, definition=definition)
    )
    checksum = _definition_checksum(definition)
    trace = [
        {
            "position": step["position"],
            "action_type": step["action_type"],
            "result": "simulated",
            "side_effect": False,
        }
        for step in definition["steps"]
    ]
    simulation = MarketingJourneySimulation(
        company_id=context.company_id,
        journey_id=journey_id,
        status="failed" if issues else "passed",
        definition_checksum=checksum,
        input_json=payload.sample_contact,
        trace_json=trace,
        issues_json=issues,
        requested_by_user_id=context.user_id,
    )
    database.add(simulation)
    await database.commit()
    await database.refresh(simulation)
    return JourneySimulationResponse(
        id=simulation.id,
        status=simulation.status,
        definition_checksum=simulation.definition_checksum,
        trace=simulation.trace_json,
        issues=simulation.issues_json,
        created_at=simulation.created_at,
    )


@router.post("/journeys/{journey_id}/publish", response_model=JourneyVersionResponse)
async def publish_journey(
    journey_id: UUID, principal: CanManageJourneys, database: DatabaseSession
) -> JourneyVersionResponse:
    context = get_request_context(principal)
    journey, definition = await _journey_definition(
        database, company_id=context.company_id, journey_id=journey_id
    )
    issues = _validate_journey(definition)
    issues.extend(
        await _content_issues(database, company_id=context.company_id, definition=definition)
    )
    checksum = _definition_checksum(definition)
    latest_simulation = await database.scalar(
        select(MarketingJourneySimulation)
        .where(
            MarketingJourneySimulation.company_id == context.company_id,
            MarketingJourneySimulation.journey_id == journey_id,
        )
        .order_by(MarketingJourneySimulation.created_at.desc())
        .limit(1)
    )
    if (
        issues
        or latest_simulation is None
        or latest_simulation.status != "passed"
        or latest_simulation.definition_checksum != checksum
    ):
        raise HTTPException(status_code=409, detail="A jornada precisa de simulação aprovada.")
    version_number = int(
        await database.scalar(
            select(func.max(MarketingJourneyVersion.version)).where(
                MarketingJourneyVersion.journey_id == journey_id
            )
        )
        or 0
    ) + 1
    version = MarketingJourneyVersion(
        company_id=context.company_id,
        journey_id=journey_id,
        version=version_number,
        definition_json=definition,
        checksum=checksum,
        published_by_user_id=context.user_id,
    )
    database.add(version)
    journey.status = "active"
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="marketing.journey.published",
        target_type="marketing_journey",
        target_id=journey.id,
        details={"version": version_number, "checksum": version.checksum},
    )
    await database.commit()
    await database.refresh(version)
    return JourneyVersionResponse(
        id=version.id,
        journey_id=journey_id,
        version=version.version,
        status=version.status,
        checksum=version.checksum,
        definition=version.definition_json,
        published_at=version.published_at,
    )


@router.post(
    "/experiments/{experiment_id}/evidence",
    response_model=ExperimentEvidenceResponse,
)
async def upsert_experiment_evidence(
    experiment_id: UUID,
    payload: ExperimentEvidenceCreate,
    principal: CanManageGrowth,
    database: DatabaseSession,
) -> ExperimentEvidenceResponse:
    context = get_request_context(principal)
    experiment = await database.scalar(
        select(MarketingExperiment).where(
            MarketingExperiment.id == experiment_id,
            MarketingExperiment.company_id == context.company_id,
        )
    )
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experimento não encontrado.")
    variant_keys = {str(item.get("key")) for item in experiment.variants}
    if payload.variant_key not in variant_keys:
        raise HTTPException(status_code=422, detail="Variante não pertence ao experimento.")
    evidence = await database.scalar(
        select(MarketingExperimentEvidence).where(
            MarketingExperimentEvidence.experiment_id == experiment_id,
            MarketingExperimentEvidence.variant_key == payload.variant_key,
        )
    )
    if evidence is None:
        evidence = MarketingExperimentEvidence(
            company_id=context.company_id,
            experiment_id=experiment_id,
            **payload.model_dump(),
        )
        database.add(evidence)
    else:
        for key, value in payload.model_dump().items():
            setattr(evidence, key, value)
        evidence.calculated_at = utc_now()
    await database.commit()
    await database.refresh(evidence)
    return ExperimentEvidenceResponse.model_validate(evidence, from_attributes=True)


def _recommendation_response(row: MarketingAgentRecommendation) -> MarketingAgentRecommendationResponse:
    return MarketingAgentRecommendationResponse(
        id=row.id,
        campaign_id=row.campaign_id,
        agent_id=row.agent_id,
        agent_version_id=row.agent_version_id,
        recommendation_type=row.recommendation_type,
        summary=row.summary,
        evidence=row.evidence_json,
        risk_level=row.risk_level,
        status=row.status,
        created_at=row.created_at,
    )


@router.post(
    "/agent-recommendations",
    response_model=MarketingAgentRecommendationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_recommendation(
    payload: MarketingAgentRecommendationCreate,
    principal: CanManageAgents,
    database: DatabaseSession,
) -> MarketingAgentRecommendationResponse:
    context = get_request_context(principal)
    campaign = await database.scalar(
        select(MarketingCampaign).where(
            MarketingCampaign.id == payload.campaign_id,
            MarketingCampaign.company_id == context.company_id,
            MarketingCampaign.archived_at.is_(None),
        )
    )
    agent = await database.scalar(
        select(Agent).where(
            Agent.id == payload.agent_id,
            Agent.company_id == context.company_id,
            Agent.status == "active",
        )
    )
    if campaign is None or agent is None or agent.active_version_id is None:
        raise HTTPException(status_code=422, detail="Campanha ou agente publicado inválido.")
    version = await database.scalar(
        select(AgentVersion).where(
            AgentVersion.id == agent.active_version_id,
            AgentVersion.agent_id == agent.id,
            AgentVersion.company_id == context.company_id,
            AgentVersion.status == "published",
        )
    )
    if version is None:
        raise HTTPException(status_code=422, detail="O agente precisa de versão publicada.")
    totals = (
        await database.execute(
            select(
                func.coalesce(func.sum(MarketingCampaignMetric.clicks), 0),
                func.coalesce(func.sum(MarketingCampaignMetric.conversions), 0),
                func.coalesce(func.sum(MarketingCampaignMetric.spend_cents), 0),
                func.coalesce(func.sum(MarketingCampaignMetric.revenue_cents), 0),
            ).where(
                MarketingCampaignMetric.company_id == context.company_id,
                MarketingCampaignMetric.campaign_id == campaign.id,
            )
        )
    ).one()
    clicks, conversions, spend, revenue = map(int, totals)
    roas = round(revenue / spend, 4) if spend else 0.0
    if spend and roas < 1:
        recommendation_type = "review_budget"
        summary = "Revise orçamento e segmentação: o retorno está abaixo do investimento."
        risk = "high"
    elif clicks and conversions / clicks < 0.02:
        recommendation_type = "improve_conversion"
        summary = "Teste nova proposta e landing page para elevar a conversão."
        risk = "medium"
    else:
        recommendation_type = "maintain_and_test"
        summary = "Mantenha a campanha e execute um teste controlado antes de ampliar investimento."
        risk = "low"
    row = MarketingAgentRecommendation(
        company_id=context.company_id,
        campaign_id=campaign.id,
        agent_id=agent.id,
        agent_version_id=version.id,
        recommendation_type=recommendation_type,
        summary=summary,
        evidence_json={
            "clicks": clicks,
            "conversions": conversions,
            "spend_cents": spend,
            "revenue_cents": revenue,
            "roas": roas,
            "source": "marketing_campaign_metrics",
        },
        risk_level=risk,
        requested_by_user_id=context.user_id,
    )
    database.add(row)
    await database.commit()
    await database.refresh(row)
    return _recommendation_response(row)


@router.patch(
    "/agent-recommendations/{recommendation_id}",
    response_model=MarketingAgentRecommendationResponse,
)
async def decide_agent_recommendation(
    recommendation_id: UUID,
    payload: MarketingAgentRecommendationDecision,
    principal: CanManageAgents,
    database: DatabaseSession,
) -> MarketingAgentRecommendationResponse:
    context = get_request_context(principal)
    row = await database.scalar(
        select(MarketingAgentRecommendation).where(
            MarketingAgentRecommendation.id == recommendation_id,
            MarketingAgentRecommendation.company_id == context.company_id,
            MarketingAgentRecommendation.status == "proposed",
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Recomendação pendente não encontrada.")
    row.status = "approved" if payload.decision == "approve" else "dismissed"
    row.decided_by_user_id = context.user_id
    row.decided_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action=f"marketing.agent_recommendation.{row.status}",
        target_type="marketing_agent_recommendation",
        target_id=row.id,
        details={"risk_level": row.risk_level, "no_side_effect": True},
    )
    await database.commit()
    return _recommendation_response(row)
