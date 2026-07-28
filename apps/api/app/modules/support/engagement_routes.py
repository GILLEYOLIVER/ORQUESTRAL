from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.modularity.dependencies import require_active_module
from app.modules.support.engagement_models import (
    SupportResponseTemplate,
    SupportSatisfactionSurvey,
)
from app.modules.support.engagement_schemas import (
    SupportGuidedResponseCreate,
    SupportGuidedResponseResult,
    SupportKnowledgeSearchResponse,
    SupportResponseTemplateCreate,
    SupportResponseTemplateResponse,
    SupportSatisfactionSummary,
    SupportSatisfactionSurveyCreate,
    SupportSatisfactionSurveyResponse,
)
from app.modules.support.engagement_service import (
    citation_model,
    protected_digest,
    satisfaction_summary_for_company,
    search_support_knowledge,
    validated_citations,
)
from app.modules.support.models import SupportInteraction, SupportTicket, SupportTicketEvent

router = APIRouter(prefix="/support/engagement", tags=["support-engagement"])
CanView = Annotated[Principal, Depends(require_permission("support.tickets.view"))]
CanComment = Annotated[Principal, Depends(require_permission("support.tickets.comment"))]
CanUpdate = Annotated[Principal, Depends(require_permission("support.tickets.update"))]
ActiveSupport = Annotated[object, Depends(require_active_module("support"))]


async def _ticket(
    database: DatabaseSession, company_id: UUID, ticket_id: UUID
) -> SupportTicket:
    ticket: SupportTicket | None = await database.scalar(
        select(SupportTicket).where(
            SupportTicket.id == ticket_id,
            SupportTicket.company_id == company_id,
        )
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Chamado não encontrado.")
    return ticket


@router.get("/templates", response_model=list[SupportResponseTemplateResponse])
async def list_templates(
    principal: CanView,
    _: ActiveSupport,
    database: DatabaseSession,
    kind: str | None = Query(default=None, pattern=r"^(macro|quick_response)$"),
) -> list[SupportResponseTemplateResponse]:
    context = get_request_context(principal)
    statement = select(SupportResponseTemplate).where(
        SupportResponseTemplate.company_id == context.company_id,
        SupportResponseTemplate.is_active.is_(True),
    )
    if kind:
        statement = statement.where(SupportResponseTemplate.kind == kind)
    templates = list(
        await database.scalars(
            statement.order_by(
                SupportResponseTemplate.usage_count.desc(),
                SupportResponseTemplate.name,
            )
        )
    )
    return [
        SupportResponseTemplateResponse.model_validate(item, from_attributes=True)
        for item in templates
    ]


@router.post(
    "/templates",
    response_model=SupportResponseTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    payload: SupportResponseTemplateCreate,
    principal: CanUpdate,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportResponseTemplateResponse:
    context = get_request_context(principal)
    exists = await database.scalar(
        select(SupportResponseTemplate.id).where(
            SupportResponseTemplate.company_id == context.company_id,
            SupportResponseTemplate.shortcut == payload.shortcut,
        )
    )
    if exists:
        raise HTTPException(status_code=409, detail="Este atalho já está em uso.")
    template = SupportResponseTemplate(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    database.add(template)
    await database.commit()
    await database.refresh(template)
    return SupportResponseTemplateResponse.model_validate(template, from_attributes=True)


@router.get("/knowledge", response_model=SupportKnowledgeSearchResponse)
async def search_knowledge_for_support(
    principal: CanView,
    _: ActiveSupport,
    database: DatabaseSession,
    q: str = Query(min_length=2, max_length=500),
    limit: int = Query(default=5, ge=1, le=10),
) -> SupportKnowledgeSearchResponse:
    context = get_request_context(principal)
    return SupportKnowledgeSearchResponse(
        query=q,
        citations=await search_support_knowledge(
            database, company_id=context.company_id, query=q, limit=limit
        ),
    )


@router.post(
    "/tickets/{ticket_id}/responses",
    response_model=SupportGuidedResponseResult,
    status_code=status.HTTP_201_CREATED,
)
async def send_guided_response(
    ticket_id: UUID,
    payload: SupportGuidedResponseCreate,
    principal: CanComment,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportGuidedResponseResult:
    context = get_request_context(principal)
    ticket = await _ticket(database, context.company_id, ticket_id)
    try:
        chunks = await validated_citations(
            database, company_id=context.company_id, citations=payload.citations
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    template = None
    if payload.template_id:
        template = await database.scalar(
            select(SupportResponseTemplate).where(
                SupportResponseTemplate.id == payload.template_id,
                SupportResponseTemplate.company_id == context.company_id,
                SupportResponseTemplate.is_active.is_(True),
            )
        )
        if not template:
            raise HTTPException(status_code=422, detail="Modelo de resposta inválido.")
    interaction = SupportInteraction(
        company_id=context.company_id,
        ticket_id=ticket.id,
        author_user_id=context.user_id,
        message=payload.message,
        is_internal=payload.is_internal,
    )
    database.add(interaction)
    await database.flush()
    for chunk in chunks:
        database.add(
            citation_model(
                company_id=context.company_id,
                ticket_id=ticket.id,
                interaction_id=interaction.id,
                user_id=context.user_id,
                chunk=chunk,
            )
        )
    if template:
        template.usage_count += 1
    database.add(
        SupportTicketEvent(
            company_id=context.company_id,
            ticket_id=ticket.id,
            actor_user_id=context.user_id,
            event_type="guided_response_sent",
            description="Resposta orientada enviada.",
            details={
                "citation_count": len(chunks),
                "template_kind": template.kind if template else None,
                "internal": payload.is_internal,
            },
        )
    )
    await database.commit()
    return SupportGuidedResponseResult(
        interaction_id=interaction.id, citations_recorded=len(chunks)
    )


@router.post(
    "/tickets/{ticket_id}/satisfaction",
    response_model=SupportSatisfactionSurveyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_satisfaction_survey(
    ticket_id: UUID,
    payload: SupportSatisfactionSurveyCreate,
    principal: CanUpdate,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportSatisfactionSurveyResponse:
    context = get_request_context(principal)
    ticket = await _ticket(database, context.company_id, ticket_id)
    if ticket.status not in {"resolved", "closed"}:
        raise HTTPException(
            status_code=409,
            detail="A avaliação exige um chamado resolvido ou fechado.",
        )
    exists = await database.scalar(
        select(SupportSatisfactionSurvey.id).where(
            SupportSatisfactionSurvey.company_id == context.company_id,
            SupportSatisfactionSurvey.ticket_id == ticket.id,
        )
    )
    if exists:
        raise HTTPException(status_code=409, detail="Este chamado já foi avaliado.")
    survey = SupportSatisfactionSurvey(
        company_id=context.company_id,
        ticket_id=ticket.id,
        recorded_by_user_id=context.user_id,
        overall_score=payload.overall_score,
        resolution_score=payload.resolution_score,
        effort_score=payload.effort_score,
        comment_sha256=protected_digest(payload.comment),
    )
    ticket.satisfaction_score = payload.overall_score
    ticket.satisfaction_comment = None
    database.add(survey)
    database.add(
        SupportTicketEvent(
            company_id=context.company_id,
            ticket_id=ticket.id,
            actor_user_id=context.user_id,
            event_type="satisfaction_received",
            description="Avaliação multidimensional registrada.",
            details={
                "overall_score": payload.overall_score,
                "resolution_score": payload.resolution_score,
                "effort_score": payload.effort_score,
                "comment_provided": bool(payload.comment),
            },
        )
    )
    await database.commit()
    await database.refresh(survey)
    return SupportSatisfactionSurveyResponse.model_validate(
        survey, from_attributes=True
    )


@router.get("/satisfaction/summary", response_model=SupportSatisfactionSummary)
async def satisfaction_summary(
    principal: CanView,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportSatisfactionSummary:
    context = get_request_context(principal)
    return await satisfaction_summary_for_company(database, context.company_id)
