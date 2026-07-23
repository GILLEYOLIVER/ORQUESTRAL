from __future__ import annotations

from datetime import date
from decimal import Decimal
from math import ceil
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.crm.customer_data_service import (
    customer_360,
    customer_profile_for_contact,
    sync_customer_profile,
)
from app.modules.crm.models import (
    CRMContact,
    CRMContactTag,
    CRMOpportunity,
    CRMOpportunityActivity,
    CRMPipeline,
    CRMPipelineStage,
    CRMTag,
    CustomerConsent,
)
from app.modules.crm.schemas import (
    CRMCommercialSummary,
    CRMContactCreate,
    CRMContactPage,
    CRMContactResponse,
    CRMContactUpdate,
    CRMCustomer360Response,
    CRMOpportunityActivityCreate,
    CRMOpportunityActivityResponse,
    CRMOpportunityCreate,
    CRMOpportunityResponse,
    CRMOpportunityUpdate,
    CRMPipelineCreate,
    CRMPipelineResponse,
    CRMPipelineStageResponse,
    CRMPipelineStageUpdate,
    CRMTagCreate,
    CRMTagResponse,
    CustomerConsentCreate,
    CustomerConsentResponse,
)
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.modularity.dependencies import require_active_module
from app.modules.users.models import CompanyUser

router = APIRouter(prefix="/crm", tags=["crm"])

ActiveCRM = Annotated[Principal, Depends(require_active_module("crm"))]
CanViewContacts = Annotated[Principal, Depends(require_permission("crm.contacts.view"))]
CanCreateContacts = Annotated[Principal, Depends(require_permission("crm.contacts.create"))]
CanUpdateContacts = Annotated[Principal, Depends(require_permission("crm.contacts.update"))]
CanDeleteContacts = Annotated[Principal, Depends(require_permission("crm.contacts.delete"))]


async def _validate_assignment(
    database: DatabaseSession, company_id: UUID, user_id: UUID | None
) -> None:
    if user_id is None:
        return
    membership = await database.scalar(
        select(CompanyUser.id).where(
            CompanyUser.company_id == company_id,
            CompanyUser.user_id == user_id,
            CompanyUser.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=422, detail="Responsável inválido para a empresa atual.")


async def _validate_tags(
    database: DatabaseSession, company_id: UUID, tag_ids: list[UUID]
) -> list[CRMTag]:
    unique_ids = set(tag_ids)
    tags = list(
        await database.scalars(
            select(CRMTag).where(
                CRMTag.company_id == company_id,
                CRMTag.id.in_(unique_ids),
            )
        )
    )
    if len(tags) != len(unique_ids):
        raise HTTPException(status_code=422, detail="Uma ou mais etiquetas são inválidas.")
    return tags


async def _tags_by_contact(
    database: DatabaseSession, contact_ids: list[UUID]
) -> dict[UUID, list[CRMTagResponse]]:
    if not contact_ids:
        return {}
    rows = (
        await database.execute(
            select(CRMContactTag.contact_id, CRMTag)
            .join(CRMTag, CRMTag.id == CRMContactTag.tag_id)
            .where(CRMContactTag.contact_id.in_(contact_ids))
            .order_by(CRMTag.name)
        )
    ).all()
    result: dict[UUID, list[CRMTagResponse]] = {}
    for contact_id, tag in rows:
        result.setdefault(contact_id, []).append(
            CRMTagResponse.model_validate(tag, from_attributes=True)
        )
    return result


def _contact_response(contact: CRMContact, tags: list[CRMTagResponse]) -> CRMContactResponse:
    return CRMContactResponse(
        id=contact.id,
        name=contact.name,
        email=contact.email,
        phone=contact.phone,
        company_name=contact.company_name,
        job_title=contact.job_title,
        source=contact.source,
        status=contact.status,
        assigned_user_id=contact.assigned_user_id,
        tags=tags,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


async def _get_contact(database: DatabaseSession, company_id: UUID, contact_id: UUID) -> CRMContact:
    contact = await database.scalar(
        select(CRMContact).where(
            CRMContact.id == contact_id,
            CRMContact.company_id == company_id,
            CRMContact.deleted_at.is_(None),
        )
    )
    if contact is None:
        raise HTTPException(status_code=404, detail="Contato não encontrado.")
    return contact


@router.get("/contacts", response_model=CRMContactPage)
async def list_contacts(
    principal: CanViewContacts,
    _: ActiveCRM,
    database: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=160)] = None,
    contact_status: Annotated[
        Literal["lead", "prospect", "customer", "inactive"] | None,
        Query(alias="status"),
    ] = None,
    source: Annotated[str | None, Query(max_length=80)] = None,
    assigned_user_id: UUID | None = None,
    tag_id: UUID | None = None,
    sort_by: Literal["name", "company_name", "status", "created_at", "updated_at"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
) -> CRMContactPage:
    context = get_request_context(principal)
    filters = [
        CRMContact.company_id == context.company_id,
        CRMContact.deleted_at.is_(None),
    ]
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                CRMContact.name.ilike(pattern),
                CRMContact.email.ilike(pattern),
                CRMContact.phone.ilike(pattern),
                CRMContact.company_name.ilike(pattern),
            )
        )
    if contact_status:
        filters.append(CRMContact.status == contact_status)
    if source:
        filters.append(CRMContact.source == source)
    if assigned_user_id:
        filters.append(CRMContact.assigned_user_id == assigned_user_id)
    if tag_id:
        filters.append(
            CRMContact.id.in_(
                select(CRMContactTag.contact_id).where(CRMContactTag.tag_id == tag_id)
            )
        )

    total = int(
        await database.scalar(select(func.count()).select_from(CRMContact).where(*filters)) or 0
    )
    sort_columns = {
        "name": CRMContact.name,
        "company_name": CRMContact.company_name,
        "status": CRMContact.status,
        "created_at": CRMContact.created_at,
        "updated_at": CRMContact.updated_at,
    }
    sort_column = sort_columns[sort_by]
    order = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    contacts = list(
        await database.scalars(
            select(CRMContact)
            .where(*filters)
            .order_by(order, CRMContact.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    tags = await _tags_by_contact(database, [contact.id for contact in contacts])
    return CRMContactPage(
        items=[_contact_response(contact, tags.get(contact.id, [])) for contact in contacts],
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total else 0,
    )


@router.post("/contacts", response_model=CRMContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    payload: CRMContactCreate,
    principal: CanCreateContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMContactResponse:
    context = get_request_context(principal)
    await _validate_assignment(database, context.company_id, payload.assigned_user_id)
    tags = await _validate_tags(database, context.company_id, payload.tag_ids)
    contact = CRMContact(
        company_id=context.company_id,
        **payload.model_dump(exclude={"tag_ids"}),
    )
    database.add(contact)
    await database.flush()
    profile = await sync_customer_profile(
        database,
        contact=contact,
        actor_user_id=context.user_id,
    )
    database.add_all(CRMContactTag(contact_id=contact.id, tag_id=tag.id) for tag in tags)
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="crm.contact.created",
        target_type="crm_contact",
        target_id=contact.id,
        details={"fields": sorted(payload.model_fields_set)},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="crm.contact.created",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="internal",
            payload={"contact_id": str(contact.id), "profile_id": str(profile.id)},
        ),
    )
    await database.commit()
    tag_responses = [CRMTagResponse.model_validate(tag, from_attributes=True) for tag in tags]
    return _contact_response(contact, tag_responses)


@router.get("/contacts/{contact_id}", response_model=CRMContactResponse)
async def get_contact(
    contact_id: UUID,
    principal: CanViewContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMContactResponse:
    context = get_request_context(principal)
    contact = await _get_contact(database, context.company_id, contact_id)
    tags = await _tags_by_contact(database, [contact.id])
    return _contact_response(contact, tags.get(contact.id, []))


@router.patch("/contacts/{contact_id}", response_model=CRMContactResponse)
async def update_contact(
    contact_id: UUID,
    payload: CRMContactUpdate,
    principal: CanUpdateContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMContactResponse:
    context = get_request_context(principal)
    contact = await _get_contact(database, context.company_id, contact_id)
    if "assigned_user_id" in payload.model_fields_set:
        await _validate_assignment(database, context.company_id, payload.assigned_user_id)

    tag_models: list[CRMTag] | None = None
    if payload.tag_ids is not None:
        tag_models = await _validate_tags(database, context.company_id, payload.tag_ids)
        await database.execute(delete(CRMContactTag).where(CRMContactTag.contact_id == contact.id))
        database.add_all(CRMContactTag(contact_id=contact.id, tag_id=tag.id) for tag in tag_models)
    for field, value in payload.model_dump(exclude_unset=True, exclude={"tag_ids"}).items():
        setattr(contact, field, value)
    contact.updated_at = utc_now()
    profile = await sync_customer_profile(
        database,
        contact=contact,
        actor_user_id=context.user_id,
    )
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="crm.contact.updated",
        target_type="crm_contact",
        target_id=contact.id,
        details={"fields": sorted(payload.model_fields_set)},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="crm.contact.updated",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="internal",
            payload={"contact_id": str(contact.id), "profile_id": str(profile.id)},
        ),
    )
    await database.commit()
    await database.refresh(contact)
    tags = await _tags_by_contact(database, [contact.id])
    return _contact_response(contact, tags.get(contact.id, []))


@router.get(
    "/contacts/{contact_id}/customer-360",
    response_model=CRMCustomer360Response,
)
async def get_customer_360(
    contact_id: UUID,
    principal: CanViewContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMCustomer360Response:
    context = get_request_context(principal)
    contact = await _get_contact(database, context.company_id, contact_id)
    try:
        return await customer_360(database, contact=contact)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/contacts/{contact_id}/consents",
    response_model=CustomerConsentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_customer_consent(
    contact_id: UUID,
    payload: CustomerConsentCreate,
    principal: CanUpdateContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CustomerConsent:
    context = get_request_context(principal)
    await _get_contact(database, context.company_id, contact_id)
    try:
        profile = await customer_profile_for_contact(
            database,
            company_id=context.company_id,
            contact_id=contact_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    captured_at = utc_now()
    if payload.expires_at is not None and payload.expires_at <= captured_at:
        raise HTTPException(status_code=422, detail="A expiração deve estar no futuro.")
    consent = CustomerConsent(
        company_id=context.company_id,
        profile_id=profile.id,
        captured_at=captured_at,
        recorded_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    database.add(consent)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="crm.customer_consent.recorded",
        target_type="customer_consent",
        target_id=consent.id,
        details={
            "profile_id": str(profile.id),
            "purpose": consent.purpose,
            "status": consent.status,
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="customer.consent.recorded",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="confidential",
            payload={
                "profile_id": str(profile.id),
                "consent_id": str(consent.id),
                "purpose": consent.purpose,
                "status": consent.status,
            },
        ),
    )
    await database.commit()
    await database.refresh(consent)
    return consent


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: UUID,
    principal: CanDeleteContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> Response:
    context = get_request_context(principal)
    contact = await _get_contact(database, context.company_id, contact_id)
    contact.deleted_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="crm.contact.deleted",
        target_type="crm_contact",
        target_id=contact.id,
        details={},
    )
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _get_pipeline(
    database: DatabaseSession, company_id: UUID, pipeline_id: UUID
) -> CRMPipeline:
    pipeline = await database.scalar(
        select(CRMPipeline).where(
            CRMPipeline.id == pipeline_id,
            CRMPipeline.company_id == company_id,
        )
    )
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Funil comercial não encontrado.")
    return pipeline


async def _get_stage(
    database: DatabaseSession,
    company_id: UUID,
    pipeline_id: UUID,
    stage_id: UUID,
) -> CRMPipelineStage:
    stage = await database.scalar(
        select(CRMPipelineStage).where(
            CRMPipelineStage.id == stage_id,
            CRMPipelineStage.company_id == company_id,
            CRMPipelineStage.pipeline_id == pipeline_id,
        )
    )
    if stage is None:
        raise HTTPException(status_code=422, detail="A etapa não pertence ao funil informado.")
    return stage


async def _get_opportunity(
    database: DatabaseSession, company_id: UUID, opportunity_id: UUID
) -> CRMOpportunity:
    opportunity = await database.scalar(
        select(CRMOpportunity).where(
            CRMOpportunity.id == opportunity_id,
            CRMOpportunity.company_id == company_id,
            CRMOpportunity.deleted_at.is_(None),
        )
    )
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada.")
    return opportunity


def _stage_response(stage: CRMPipelineStage) -> CRMPipelineStageResponse:
    return CRMPipelineStageResponse.model_validate(stage, from_attributes=True)


async def _pipeline_response(
    database: DatabaseSession, pipeline: CRMPipeline
) -> CRMPipelineResponse:
    stages = list(
        await database.scalars(
            select(CRMPipelineStage)
            .where(CRMPipelineStage.pipeline_id == pipeline.id)
            .order_by(CRMPipelineStage.position, CRMPipelineStage.created_at)
        )
    )
    opportunities = list(
        await database.scalars(
            select(CRMOpportunity).where(
                CRMOpportunity.pipeline_id == pipeline.id,
                CRMOpportunity.deleted_at.is_(None),
            )
        )
    )
    open_opportunities = [item for item in opportunities if item.status == "open"]
    return CRMPipelineResponse(
        id=pipeline.id,
        name=pipeline.name,
        is_default=pipeline.is_default,
        stages=[_stage_response(stage) for stage in stages],
        opportunity_count=len(opportunities),
        open_value=sum((item.amount for item in open_opportunities), Decimal("0")),
        created_at=pipeline.created_at,
        updated_at=pipeline.updated_at,
    )


async def _opportunity_response(
    database: DatabaseSession, opportunity: CRMOpportunity
) -> CRMOpportunityResponse:
    pipeline = await database.get(CRMPipeline, opportunity.pipeline_id)
    stage = await database.get(CRMPipelineStage, opportunity.stage_id)
    contact = (
        await database.get(CRMContact, opportunity.contact_id)
        if opportunity.contact_id is not None
        else None
    )
    if pipeline is None or stage is None:
        raise HTTPException(
            status_code=409, detail="O funil desta oportunidade está inconsistente."
        )
    return CRMOpportunityResponse(
        id=opportunity.id,
        pipeline_id=opportunity.pipeline_id,
        pipeline_name=pipeline.name,
        stage_id=opportunity.stage_id,
        stage_name=stage.name,
        stage_probability=stage.probability,
        contact_id=opportunity.contact_id,
        contact_name=contact.name if contact is not None else None,
        assigned_user_id=opportunity.assigned_user_id,
        title=opportunity.title,
        amount=opportunity.amount,
        probability=opportunity.probability,
        expected_close_date=opportunity.expected_close_date,
        source=opportunity.source,
        status=opportunity.status,
        lost_reason=opportunity.lost_reason,
        notes=opportunity.notes,
        closed_at=opportunity.closed_at,
        created_at=opportunity.created_at,
        updated_at=opportunity.updated_at,
    )


def _activity_response(activity: CRMOpportunityActivity) -> CRMOpportunityActivityResponse:
    return CRMOpportunityActivityResponse.model_validate(activity, from_attributes=True)


async def _ensure_default_pipeline(database: DatabaseSession, company_id: UUID) -> CRMPipeline:
    pipeline = await database.scalar(
        select(CRMPipeline)
        .where(CRMPipeline.company_id == company_id)
        .order_by(CRMPipeline.is_default.desc(), CRMPipeline.created_at)
    )
    if pipeline is not None:
        return pipeline

    pipeline = CRMPipeline(company_id=company_id, name="Funil de vendas", is_default=True)
    database.add(pipeline)
    await database.flush()
    default_stages = (
        ("Novo contato", 0, 10, "#2f6f64"),
        ("Qualificação", 1, 30, "#d69f40"),
        ("Proposta", 2, 60, "#cf7246"),
        ("Negociação", 3, 80, "#377c8c"),
        ("Fechamento", 4, 100, "#2d8659"),
    )
    for name, position, probability, color in default_stages:
        database.add(
            CRMPipelineStage(
                company_id=company_id,
                pipeline_id=pipeline.id,
                name=name,
                position=position,
                probability=probability,
                color=color,
            )
        )
    await database.commit()
    await database.refresh(pipeline)
    return pipeline


@router.get("/summary", response_model=CRMCommercialSummary)
async def commercial_summary(
    principal: CanViewContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMCommercialSummary:
    context = get_request_context(principal)
    pipelines = list(
        await database.scalars(
            select(CRMPipeline).where(CRMPipeline.company_id == context.company_id)
        )
    )
    if not pipelines:
        await _ensure_default_pipeline(database, context.company_id)
        pipelines = list(
            await database.scalars(
                select(CRMPipeline).where(CRMPipeline.company_id == context.company_id)
            )
        )
    opportunities = list(
        await database.scalars(
            select(CRMOpportunity).where(
                CRMOpportunity.company_id == context.company_id,
                CRMOpportunity.deleted_at.is_(None),
            )
        )
    )
    open_items = [item for item in opportunities if item.status == "open"]
    stages = {
        stage.id: stage
        for stage in list(
            await database.scalars(
                select(CRMPipelineStage).where(CRMPipelineStage.company_id == context.company_id)
            )
        )
    }
    weighted_forecast = sum(
        (
            item.amount
            * Decimal(
                item.probability
                if item.probability is not None
                else stages[item.stage_id].probability
            )
            / Decimal("100")
            for item in open_items
            if item.stage_id in stages
        ),
        Decimal("0"),
    )
    return CRMCommercialSummary(
        pipeline_count=len(pipelines),
        open_opportunities=len(open_items),
        open_value=sum((item.amount for item in open_items), Decimal("0")),
        won_opportunities=sum(item.status == "won" for item in opportunities),
        lost_opportunities=sum(item.status == "lost" for item in opportunities),
        overdue_opportunities=sum(
            item.expected_close_date is not None and item.expected_close_date < date.today()
            for item in open_items
        ),
        weighted_forecast=weighted_forecast,
    )


@router.get("/pipelines", response_model=list[CRMPipelineResponse])
async def list_pipelines(
    principal: CanViewContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[CRMPipelineResponse]:
    context = get_request_context(principal)
    await _ensure_default_pipeline(database, context.company_id)
    pipelines = list(
        await database.scalars(
            select(CRMPipeline)
            .where(CRMPipeline.company_id == context.company_id)
            .order_by(CRMPipeline.is_default.desc(), CRMPipeline.created_at)
        )
    )
    return [await _pipeline_response(database, pipeline) for pipeline in pipelines]


@router.post("/pipelines", response_model=CRMPipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    payload: CRMPipelineCreate,
    principal: CanCreateContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMPipelineResponse:
    context = get_request_context(principal)
    existing = await database.scalar(
        select(CRMPipeline.id).where(
            CRMPipeline.company_id == context.company_id,
            func.lower(CRMPipeline.name) == payload.name.lower(),
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Já existe um funil com este nome.")
    has_pipeline = await database.scalar(
        select(CRMPipeline.id).where(CRMPipeline.company_id == context.company_id).limit(1)
    )
    pipeline = CRMPipeline(
        company_id=context.company_id,
        name=payload.name,
        is_default=has_pipeline is None,
    )
    database.add(pipeline)
    await database.flush()
    for stage_payload in sorted(payload.stages, key=lambda item: item.position):
        database.add(
            CRMPipelineStage(
                company_id=context.company_id,
                pipeline_id=pipeline.id,
                **stage_payload.model_dump(),
            )
        )
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Não foi possível criar o funil.") from exc
    await database.refresh(pipeline)
    return await _pipeline_response(database, pipeline)


@router.patch(
    "/pipelines/{pipeline_id}/stages/{stage_id}",
    response_model=CRMPipelineStageResponse,
)
async def update_pipeline_stage(
    pipeline_id: UUID,
    stage_id: UUID,
    payload: CRMPipelineStageUpdate,
    principal: CanUpdateContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMPipelineStageResponse:
    context = get_request_context(principal)
    await _get_pipeline(database, context.company_id, pipeline_id)
    stage = await _get_stage(database, context.company_id, pipeline_id, stage_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(stage, field, value)
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Já existe uma etapa com este nome.") from exc
    await database.refresh(stage)
    return _stage_response(stage)


@router.get("/opportunities", response_model=list[CRMOpportunityResponse])
async def list_opportunities(
    principal: CanViewContacts,
    _: ActiveCRM,
    database: DatabaseSession,
    pipeline_id: UUID | None = None,
    stage_id: UUID | None = None,
    opportunity_status: Annotated[
        Literal["open", "won", "lost"] | None, Query(alias="status")
    ] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> list[CRMOpportunityResponse]:
    context = get_request_context(principal)
    query = select(CRMOpportunity).where(
        CRMOpportunity.company_id == context.company_id,
        CRMOpportunity.deleted_at.is_(None),
    )
    if pipeline_id is not None:
        query = query.where(CRMOpportunity.pipeline_id == pipeline_id)
    if stage_id is not None:
        query = query.where(CRMOpportunity.stage_id == stage_id)
    if opportunity_status is not None:
        query = query.where(CRMOpportunity.status == opportunity_status)
    if search:
        query = query.where(CRMOpportunity.title.ilike(f"%{search.strip()}%"))
    opportunities = list(await database.scalars(query.order_by(CRMOpportunity.updated_at.desc())))
    return [await _opportunity_response(database, item) for item in opportunities]


@router.post(
    "/opportunities",
    response_model=CRMOpportunityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_opportunity(
    payload: CRMOpportunityCreate,
    principal: CanCreateContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMOpportunityResponse:
    context = get_request_context(principal)
    await _get_pipeline(database, context.company_id, payload.pipeline_id)
    await _get_stage(database, context.company_id, payload.pipeline_id, payload.stage_id)
    if payload.contact_id is not None:
        await _get_contact(database, context.company_id, payload.contact_id)
    await _validate_assignment(database, context.company_id, payload.assigned_user_id)
    opportunity = CRMOpportunity(company_id=context.company_id, **payload.model_dump())
    database.add(opportunity)
    await database.flush()
    database.add(
        CRMOpportunityActivity(
            company_id=context.company_id,
            opportunity_id=opportunity.id,
            contact_id=opportunity.contact_id,
            actor_user_id=context.user_id,
            activity_type="status_change",
            subject="Oportunidade criada",
            body="A oportunidade entrou no funil comercial.",
        )
    )
    await database.commit()
    await database.refresh(opportunity)
    return await _opportunity_response(database, opportunity)


@router.get("/opportunities/{opportunity_id}", response_model=CRMOpportunityResponse)
async def get_opportunity(
    opportunity_id: UUID,
    principal: CanViewContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMOpportunityResponse:
    context = get_request_context(principal)
    opportunity = await _get_opportunity(database, context.company_id, opportunity_id)
    return await _opportunity_response(database, opportunity)


@router.patch("/opportunities/{opportunity_id}", response_model=CRMOpportunityResponse)
async def update_opportunity(
    opportunity_id: UUID,
    payload: CRMOpportunityUpdate,
    principal: CanUpdateContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMOpportunityResponse:
    context = get_request_context(principal)
    opportunity = await _get_opportunity(database, context.company_id, opportunity_id)
    changes = payload.model_dump(exclude_unset=True)
    target_pipeline_id = changes.get("pipeline_id", opportunity.pipeline_id)
    target_stage_id = changes.get("stage_id", opportunity.stage_id)
    await _get_pipeline(database, context.company_id, target_pipeline_id)
    target_stage = await _get_stage(
        database, context.company_id, target_pipeline_id, target_stage_id
    )
    if "contact_id" in changes and changes["contact_id"] is not None:
        await _get_contact(database, context.company_id, changes["contact_id"])
    if "assigned_user_id" in changes:
        await _validate_assignment(database, context.company_id, changes["assigned_user_id"])

    previous_stage_id = opportunity.stage_id
    previous_status = opportunity.status
    for field, value in changes.items():
        setattr(opportunity, field, value)
    if opportunity.status in {"won", "lost"}:
        opportunity.closed_at = opportunity.closed_at or utc_now()
    elif opportunity.status == "open":
        opportunity.closed_at = None

    if previous_stage_id != opportunity.stage_id:
        database.add(
            CRMOpportunityActivity(
                company_id=context.company_id,
                opportunity_id=opportunity.id,
                contact_id=opportunity.contact_id,
                actor_user_id=context.user_id,
                activity_type="stage_change",
                subject=f"Movida para {target_stage.name}",
            )
        )
    if previous_status != opportunity.status:
        database.add(
            CRMOpportunityActivity(
                company_id=context.company_id,
                opportunity_id=opportunity.id,
                contact_id=opportunity.contact_id,
                actor_user_id=context.user_id,
                activity_type="status_change",
                subject=f"Status alterado para {opportunity.status}",
                body=opportunity.lost_reason if opportunity.status == "lost" else None,
            )
        )
    await database.commit()
    await database.refresh(opportunity)
    return await _opportunity_response(database, opportunity)


@router.delete("/opportunities/{opportunity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_opportunity(
    opportunity_id: UUID,
    principal: CanDeleteContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> Response:
    context = get_request_context(principal)
    opportunity = await _get_opportunity(database, context.company_id, opportunity_id)
    opportunity.deleted_at = utc_now()
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/opportunities/{opportunity_id}/activities",
    response_model=list[CRMOpportunityActivityResponse],
)
async def list_opportunity_activities(
    opportunity_id: UUID,
    principal: CanViewContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[CRMOpportunityActivityResponse]:
    context = get_request_context(principal)
    await _get_opportunity(database, context.company_id, opportunity_id)
    activities = list(
        await database.scalars(
            select(CRMOpportunityActivity)
            .where(
                CRMOpportunityActivity.company_id == context.company_id,
                CRMOpportunityActivity.opportunity_id == opportunity_id,
            )
            .order_by(CRMOpportunityActivity.occurred_at.desc())
        )
    )
    return [_activity_response(activity) for activity in activities]


@router.post(
    "/opportunities/{opportunity_id}/activities",
    response_model=CRMOpportunityActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_opportunity_activity(
    opportunity_id: UUID,
    payload: CRMOpportunityActivityCreate,
    principal: CanUpdateContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMOpportunityActivityResponse:
    context = get_request_context(principal)
    opportunity = await _get_opportunity(database, context.company_id, opportunity_id)
    activity = CRMOpportunityActivity(
        company_id=context.company_id,
        opportunity_id=opportunity.id,
        contact_id=opportunity.contact_id,
        actor_user_id=context.user_id,
        activity_type=payload.activity_type,
        subject=payload.subject,
        body=payload.body,
        occurred_at=payload.occurred_at or utc_now(),
    )
    database.add(activity)
    await database.commit()
    await database.refresh(activity)
    return _activity_response(activity)


@router.get("/tags", response_model=list[CRMTagResponse])
async def list_tags(
    principal: CanViewContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> list[CRMTagResponse]:
    context = get_request_context(principal)
    tags = list(
        await database.scalars(
            select(CRMTag).where(CRMTag.company_id == context.company_id).order_by(CRMTag.name)
        )
    )
    return [CRMTagResponse.model_validate(tag, from_attributes=True) for tag in tags]


@router.post("/tags", response_model=CRMTagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    payload: CRMTagCreate,
    principal: CanUpdateContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> CRMTagResponse:
    context = get_request_context(principal)
    tag = CRMTag(company_id=context.company_id, name=payload.name)
    database.add(tag)
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Essa etiqueta já existe.") from exc
    return CRMTagResponse.model_validate(tag, from_attributes=True)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: UUID,
    principal: CanUpdateContacts,
    _: ActiveCRM,
    database: DatabaseSession,
) -> Response:
    context = get_request_context(principal)
    tag = await database.scalar(
        select(CRMTag).where(CRMTag.id == tag_id, CRMTag.company_id == context.company_id)
    )
    if tag is None:
        raise HTTPException(status_code=404, detail="Etiqueta não encontrada.")
    await database.delete(tag)
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
