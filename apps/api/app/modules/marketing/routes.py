from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.crm.models import CRMContact
from app.modules.marketing.models import (
    MarketingCampaign,
    MarketingCampaignContact,
    MarketingJourney,
    MarketingJourneyStep,
)
from app.modules.marketing.schemas import (
    CampaignAudienceCreate,
    CampaignAudienceResponse,
    CampaignAudienceUpdate,
    CampaignCreate,
    CampaignResponse,
    CampaignUpdate,
    JourneyCreate,
    JourneyResponse,
    JourneyStepCreate,
    JourneyStepResponse,
    JourneyStepUpdate,
    JourneyUpdate,
    MarketingSummaryResponse,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(
    prefix="/marketing",
    tags=["marketing"],
    dependencies=[Depends(require_active_module("marketing"))],
)
CanViewMarketing = Annotated[Principal, Depends(require_permission("marketing.view"))]
CanCreateMarketing = Annotated[Principal, Depends(require_permission("marketing.create"))]
CanUpdateMarketing = Annotated[Principal, Depends(require_permission("marketing.update"))]
CanDeleteMarketing = Annotated[Principal, Depends(require_permission("marketing.delete"))]
CanManageAudience = Annotated[Principal, Depends(require_permission("marketing.audience.manage"))]
CanManageJourneys = Annotated[Principal, Depends(require_permission("marketing.journeys.manage"))]


async def _campaign(
    database: DatabaseSession, *, campaign_id: UUID, company_id: UUID
) -> MarketingCampaign:
    campaign = await database.scalar(
        select(MarketingCampaign).where(
            MarketingCampaign.id == campaign_id,
            MarketingCampaign.company_id == company_id,
            MarketingCampaign.archived_at.is_(None),
        )
    )
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada nesta empresa.")
    return campaign


async def _campaign_response(
    database: DatabaseSession, campaign: MarketingCampaign
) -> CampaignResponse:
    audience, engaged, converted = (
        await database.execute(
            select(
                func.count(MarketingCampaignContact.id),
                func.count(MarketingCampaignContact.id).filter(
                    MarketingCampaignContact.status.in_(("engaged", "converted"))
                ),
                func.count(MarketingCampaignContact.id).filter(
                    MarketingCampaignContact.status == "converted"
                ),
            ).where(
                MarketingCampaignContact.company_id == campaign.company_id,
                MarketingCampaignContact.campaign_id == campaign.id,
            )
        )
    ).one()
    return CampaignResponse.model_validate(
        {
            "id": campaign.id,
            "name": campaign.name,
            "description": campaign.description,
            "objective": campaign.objective,
            "channel": campaign.channel,
            "status": campaign.status,
            "start_at": campaign.start_at,
            "end_at": campaign.end_at,
            "budget_cents": campaign.budget_cents,
            "spent_cents": campaign.spent_cents,
            "audience_total": int(audience or 0),
            "engaged_total": int(engaged or 0),
            "converted_total": int(converted or 0),
            "created_at": campaign.created_at,
            "updated_at": campaign.updated_at,
        }
    )


def _audience_response(item: MarketingCampaignContact) -> CampaignAudienceResponse:
    return CampaignAudienceResponse.model_validate(item, from_attributes=True)


async def _journey(
    database: DatabaseSession, *, journey_id: UUID, company_id: UUID
) -> MarketingJourney:
    journey = await database.scalar(
        select(MarketingJourney).where(
            MarketingJourney.id == journey_id,
            MarketingJourney.company_id == company_id,
            MarketingJourney.archived_at.is_(None),
        )
    )
    if journey is None:
        raise HTTPException(status_code=404, detail="Jornada nao encontrada nesta empresa.")
    return journey


async def _journey_response(
    database: DatabaseSession, journey: MarketingJourney
) -> JourneyResponse:
    step_total = int(
        await database.scalar(
            select(func.count(MarketingJourneyStep.id)).where(
                MarketingJourneyStep.company_id == journey.company_id,
                MarketingJourneyStep.journey_id == journey.id,
            )
        )
        or 0
    )
    return JourneyResponse.model_validate(
        {
            "id": journey.id,
            "name": journey.name,
            "description": journey.description,
            "trigger_type": journey.trigger_type,
            "status": journey.status,
            "step_total": step_total,
            "created_at": journey.created_at,
            "updated_at": journey.updated_at,
        }
    )


@router.get("/summary", response_model=MarketingSummaryResponse)
async def marketing_summary(
    principal: CanViewMarketing, database: DatabaseSession
) -> MarketingSummaryResponse:
    context = get_request_context(principal)
    campaigns_total = int(
        await database.scalar(
            select(func.count(MarketingCampaign.id)).where(
                MarketingCampaign.company_id == context.company_id,
                MarketingCampaign.archived_at.is_(None),
            )
        )
        or 0
    )
    campaigns_active = int(
        await database.scalar(
            select(func.count(MarketingCampaign.id)).where(
                MarketingCampaign.company_id == context.company_id,
                MarketingCampaign.archived_at.is_(None),
                MarketingCampaign.status == "active",
            )
        )
        or 0
    )
    audience_total, conversions_total = (
        await database.execute(
            select(
                func.count(MarketingCampaignContact.id),
                func.count(MarketingCampaignContact.id).filter(
                    MarketingCampaignContact.status == "converted"
                ),
            ).where(MarketingCampaignContact.company_id == context.company_id)
        )
    ).one()
    return MarketingSummaryResponse(
        campaigns_total=campaigns_total,
        campaigns_active=campaigns_active,
        audience_total=int(audience_total or 0),
        conversions_total=int(conversions_total or 0),
    )


@router.get("/campaigns", response_model=list[CampaignResponse])
async def list_campaigns(
    principal: CanViewMarketing,
    database: DatabaseSession,
    campaign_status: str | None = Query(default=None, alias="status"),
) -> list[CampaignResponse]:
    context = get_request_context(principal)
    statement = select(MarketingCampaign).where(
        MarketingCampaign.company_id == context.company_id,
        MarketingCampaign.archived_at.is_(None),
    )
    if campaign_status:
        statement = statement.where(MarketingCampaign.status == campaign_status)
    rows = list(
        await database.scalars(statement.order_by(MarketingCampaign.updated_at.desc()).limit(200))
    )
    return [await _campaign_response(database, row) for row in rows]


@router.post("/campaigns", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: CampaignCreate, principal: CanCreateMarketing, database: DatabaseSession
) -> CampaignResponse:
    context = get_request_context(principal)
    campaign = MarketingCampaign(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    database.add(campaign)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="marketing.campaign.created",
        target_type="marketing_campaign",
        target_id=campaign.id,
        details={"name": campaign.name, "channel": campaign.channel},
    )
    await database.commit()
    await database.refresh(campaign)
    return await _campaign_response(database, campaign)


@router.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: UUID, principal: CanViewMarketing, database: DatabaseSession
) -> CampaignResponse:
    context = get_request_context(principal)
    return await _campaign_response(
        database,
        await _campaign(database, campaign_id=campaign_id, company_id=context.company_id),
    )


@router.patch("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: UUID,
    payload: CampaignUpdate,
    principal: CanUpdateMarketing,
    database: DatabaseSession,
) -> CampaignResponse:
    context = get_request_context(principal)
    campaign = await _campaign(database, campaign_id=campaign_id, company_id=context.company_id)
    changes = payload.model_dump(exclude_unset=True)
    start_at = changes.get("start_at", campaign.start_at)
    end_at = changes.get("end_at", campaign.end_at)
    if start_at and end_at and end_at < start_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O encerramento deve ocorrer depois do inicio da campanha.",
        )
    for field, value in changes.items():
        setattr(campaign, field, value)
    campaign.updated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="marketing.campaign.updated",
        target_type="marketing_campaign",
        target_id=campaign.id,
        details={"fields": sorted(payload.model_fields_set)},
    )
    await database.commit()
    await database.refresh(campaign)
    return await _campaign_response(database, campaign)


@router.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_campaign(
    campaign_id: UUID, principal: CanDeleteMarketing, database: DatabaseSession
) -> Response:
    context = get_request_context(principal)
    campaign = await _campaign(database, campaign_id=campaign_id, company_id=context.company_id)
    campaign.archived_at = utc_now()
    campaign.status = "cancelled"
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="marketing.campaign.archived",
        target_type="marketing_campaign",
        target_id=campaign.id,
        details={"name": campaign.name},
    )
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/campaigns/{campaign_id}/audience", response_model=list[CampaignAudienceResponse])
async def list_campaign_audience(
    campaign_id: UUID, principal: CanViewMarketing, database: DatabaseSession
) -> list[CampaignAudienceResponse]:
    context = get_request_context(principal)
    await _campaign(database, campaign_id=campaign_id, company_id=context.company_id)
    rows = list(
        await database.scalars(
            select(MarketingCampaignContact)
            .where(
                MarketingCampaignContact.company_id == context.company_id,
                MarketingCampaignContact.campaign_id == campaign_id,
            )
            .order_by(MarketingCampaignContact.created_at.desc())
        )
    )
    return [_audience_response(row) for row in rows]


@router.post(
    "/campaigns/{campaign_id}/audience",
    response_model=CampaignAudienceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_campaign_contact(
    campaign_id: UUID,
    payload: CampaignAudienceCreate,
    principal: CanManageAudience,
    database: DatabaseSession,
) -> CampaignAudienceResponse:
    context = get_request_context(principal)
    await _campaign(database, campaign_id=campaign_id, company_id=context.company_id)
    contact = await database.scalar(
        select(CRMContact).where(
            CRMContact.id == payload.contact_id,
            CRMContact.company_id == context.company_id,
        )
    )
    if contact is None:
        raise HTTPException(status_code=404, detail="Contato nao encontrado nesta empresa.")
    existing = await database.scalar(
        select(MarketingCampaignContact).where(
            MarketingCampaignContact.campaign_id == campaign_id,
            MarketingCampaignContact.contact_id == payload.contact_id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Contato ja pertence ao publico da campanha.")
    item = MarketingCampaignContact(
        company_id=context.company_id,
        campaign_id=campaign_id,
        **payload.model_dump(),
    )
    database.add(item)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="marketing.audience.contact_added",
        target_type="marketing_campaign_contact",
        target_id=item.id,
        details={"campaign_id": str(campaign_id), "contact_id": str(payload.contact_id)},
    )
    await database.commit()
    await database.refresh(item)
    return _audience_response(item)


@router.patch(
    "/campaigns/{campaign_id}/audience/{item_id}",
    response_model=CampaignAudienceResponse,
)
async def update_campaign_contact(
    campaign_id: UUID,
    item_id: UUID,
    payload: CampaignAudienceUpdate,
    principal: CanManageAudience,
    database: DatabaseSession,
) -> CampaignAudienceResponse:
    context = get_request_context(principal)
    await _campaign(database, campaign_id=campaign_id, company_id=context.company_id)
    item = await database.scalar(
        select(MarketingCampaignContact).where(
            MarketingCampaignContact.id == item_id,
            MarketingCampaignContact.campaign_id == campaign_id,
            MarketingCampaignContact.company_id == context.company_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Contato nao encontrado no publico.")
    item.status = payload.status
    item.updated_at = utc_now()
    if payload.status in {"engaged", "converted"}:
        item.last_interaction_at = utc_now()
    await database.commit()
    await database.refresh(item)
    return _audience_response(item)


@router.delete(
    "/campaigns/{campaign_id}/audience/{item_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_campaign_contact(
    campaign_id: UUID,
    item_id: UUID,
    principal: CanManageAudience,
    database: DatabaseSession,
) -> Response:
    context = get_request_context(principal)
    await _campaign(database, campaign_id=campaign_id, company_id=context.company_id)
    item = await database.scalar(
        select(MarketingCampaignContact).where(
            MarketingCampaignContact.id == item_id,
            MarketingCampaignContact.campaign_id == campaign_id,
            MarketingCampaignContact.company_id == context.company_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Contato nao encontrado no publico.")
    await database.delete(item)
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/journeys", response_model=list[JourneyResponse])
async def list_journeys(
    principal: CanViewMarketing, database: DatabaseSession
) -> list[JourneyResponse]:
    context = get_request_context(principal)
    rows = list(
        await database.scalars(
            select(MarketingJourney)
            .where(
                MarketingJourney.company_id == context.company_id,
                MarketingJourney.archived_at.is_(None),
            )
            .order_by(MarketingJourney.updated_at.desc())
        )
    )
    return [await _journey_response(database, row) for row in rows]


@router.post("/journeys", response_model=JourneyResponse, status_code=status.HTTP_201_CREATED)
async def create_journey(
    payload: JourneyCreate, principal: CanManageJourneys, database: DatabaseSession
) -> JourneyResponse:
    context = get_request_context(principal)
    journey = MarketingJourney(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    database.add(journey)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="marketing.journey.created",
        target_type="marketing_journey",
        target_id=journey.id,
        details={"name": journey.name, "trigger_type": journey.trigger_type},
    )
    await database.commit()
    await database.refresh(journey)
    return await _journey_response(database, journey)


@router.patch("/journeys/{journey_id}", response_model=JourneyResponse)
async def update_journey(
    journey_id: UUID,
    payload: JourneyUpdate,
    principal: CanManageJourneys,
    database: DatabaseSession,
) -> JourneyResponse:
    context = get_request_context(principal)
    journey = await _journey(database, journey_id=journey_id, company_id=context.company_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(journey, field, value)
    journey.updated_at = utc_now()
    await database.commit()
    await database.refresh(journey)
    return await _journey_response(database, journey)


@router.delete("/journeys/{journey_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_journey(
    journey_id: UUID, principal: CanManageJourneys, database: DatabaseSession
) -> Response:
    context = get_request_context(principal)
    journey = await _journey(database, journey_id=journey_id, company_id=context.company_id)
    journey.status = "archived"
    journey.archived_at = utc_now()
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/journeys/{journey_id}/steps", response_model=list[JourneyStepResponse])
async def list_journey_steps(
    journey_id: UUID, principal: CanViewMarketing, database: DatabaseSession
) -> list[JourneyStepResponse]:
    context = get_request_context(principal)
    await _journey(database, journey_id=journey_id, company_id=context.company_id)
    rows = list(
        await database.scalars(
            select(MarketingJourneyStep)
            .where(
                MarketingJourneyStep.company_id == context.company_id,
                MarketingJourneyStep.journey_id == journey_id,
            )
            .order_by(MarketingJourneyStep.position)
        )
    )
    return [JourneyStepResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post(
    "/journeys/{journey_id}/steps",
    response_model=JourneyStepResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_journey_step(
    journey_id: UUID,
    payload: JourneyStepCreate,
    principal: CanManageJourneys,
    database: DatabaseSession,
) -> JourneyStepResponse:
    context = get_request_context(principal)
    await _journey(database, journey_id=journey_id, company_id=context.company_id)
    occupied = await database.scalar(
        select(MarketingJourneyStep.id).where(
            MarketingJourneyStep.journey_id == journey_id,
            MarketingJourneyStep.position == payload.position,
        )
    )
    if occupied is not None:
        raise HTTPException(status_code=409, detail="Ja existe uma etapa nesta posicao.")
    step = MarketingJourneyStep(
        company_id=context.company_id,
        journey_id=journey_id,
        **payload.model_dump(),
    )
    database.add(step)
    await database.commit()
    await database.refresh(step)
    return JourneyStepResponse.model_validate(step, from_attributes=True)


@router.patch("/journeys/{journey_id}/steps/{step_id}", response_model=JourneyStepResponse)
async def update_journey_step(
    journey_id: UUID,
    step_id: UUID,
    payload: JourneyStepUpdate,
    principal: CanManageJourneys,
    database: DatabaseSession,
) -> JourneyStepResponse:
    context = get_request_context(principal)
    await _journey(database, journey_id=journey_id, company_id=context.company_id)
    step = await database.scalar(
        select(MarketingJourneyStep).where(
            MarketingJourneyStep.id == step_id,
            MarketingJourneyStep.journey_id == journey_id,
            MarketingJourneyStep.company_id == context.company_id,
        )
    )
    if step is None:
        raise HTTPException(status_code=404, detail="Etapa nao encontrada nesta jornada.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(step, field, value)
    step.updated_at = utc_now()
    await database.commit()
    await database.refresh(step)
    return JourneyStepResponse.model_validate(step, from_attributes=True)


@router.delete("/journeys/{journey_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_journey_step(
    journey_id: UUID,
    step_id: UUID,
    principal: CanManageJourneys,
    database: DatabaseSession,
) -> Response:
    context = get_request_context(principal)
    await _journey(database, journey_id=journey_id, company_id=context.company_id)
    step = await database.scalar(
        select(MarketingJourneyStep).where(
            MarketingJourneyStep.id == step_id,
            MarketingJourneyStep.journey_id == journey_id,
            MarketingJourneyStep.company_id == context.company_id,
        )
    )
    if step is None:
        raise HTTPException(status_code=404, detail="Etapa nao encontrada nesta jornada.")
    await database.delete(step)
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
