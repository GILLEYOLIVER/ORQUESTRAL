from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utc_now
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.support.models import (
    SupportAgentCapacity,
    SupportAgentSkill,
    SupportQueue,
    SupportQueueSkill,
    SupportSkill,
    SupportTicket,
    SupportTicketEvent,
)
from app.modules.support.routing_schemas import (
    AgentSkillInput,
    SupportAgentCapacityUpsert,
    SupportQueueRoutingResponse,
    SupportQueueSkillsUpdate,
    SupportRoutingAgentResponse,
    SupportRoutingAssignmentResponse,
    SupportRoutingCandidateResponse,
    SupportRoutingConfigurationResponse,
    SupportRoutingRecommendationResponse,
    SupportRoutingRequest,
    SupportSkillCreate,
    SupportSkillResponse,
)
from app.modules.users.models import CompanyUser, User


@dataclass(frozen=True)
class RoutingCandidateInput:
    status: str
    max_active_tickets: int
    active_tickets: int
    primary_queue_matches: bool
    languages: tuple[str, ...]
    accepted_channels: tuple[str, ...]
    skill_levels: dict[UUID, int]


def score_routing_candidate(
    candidate: RoutingCandidateInput,
    *,
    channel: str,
    language_code: str | None,
    required_skill_ids: tuple[UUID, ...],
) -> tuple[int, list[str]] | None:
    if candidate.status not in {"available", "busy"}:
        return None
    if candidate.active_tickets >= candidate.max_active_tickets:
        return None
    if candidate.accepted_channels and channel not in candidate.accepted_channels:
        return None
    if language_code and candidate.languages and language_code not in candidate.languages:
        base_language = language_code.split("-", 1)[0]
        if base_language not in candidate.languages:
            return None
    if any(skill_id not in candidate.skill_levels for skill_id in required_skill_ids):
        return None

    reasons: list[str] = []
    score = 40 if candidate.status == "available" else 15
    reasons.append(
        "Disponível para receber atendimento"
        if candidate.status == "available"
        else "Disponível com carga em andamento"
    )
    if candidate.primary_queue_matches:
        score += 8
        reasons.append("Fila principal compatível")
    if language_code:
        score += 10
        reasons.append(f"Atende em {language_code}")
    if required_skill_ids:
        proficiency = min(candidate.skill_levels[item] for item in required_skill_ids)
        score += proficiency * 10
        reasons.append(f"Habilidade compatível no nível {proficiency}")
    load_percent = round(candidate.active_tickets * 100 / candidate.max_active_tickets)
    score -= round(load_percent * 0.3)
    reasons.append(f"Carga atual de {candidate.active_tickets}/{candidate.max_active_tickets}")
    return score, reasons


async def _ticket(database: AsyncSession, company_id: UUID, ticket_id: UUID) -> SupportTicket:
    ticket = await database.scalar(
        select(SupportTicket).where(
            SupportTicket.company_id == company_id,
            SupportTicket.id == ticket_id,
        )
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail="Chamado não encontrado.")
    return ticket


async def _skill_ids_exist(
    database: AsyncSession,
    company_id: UUID,
    skill_ids: set[UUID],
) -> bool:
    if not skill_ids:
        return True
    count = await database.scalar(
        select(func.count(SupportSkill.id)).where(
            SupportSkill.company_id == company_id,
            SupportSkill.id.in_(skill_ids),
            SupportSkill.is_active.is_(True),
        )
    )
    return int(count or 0) == len(skill_ids)


async def routing_configuration(
    database: AsyncSession, company_id: UUID
) -> SupportRoutingConfigurationResponse:
    skills = list(
        await database.scalars(
            select(SupportSkill)
            .where(
                SupportSkill.company_id == company_id,
                SupportSkill.is_active.is_(True),
            )
            .order_by(SupportSkill.name)
        )
    )
    queues = list(
        await database.scalars(
            select(SupportQueue)
            .where(
                SupportQueue.company_id == company_id,
                SupportQueue.is_active.is_(True),
            )
            .order_by(SupportQueue.name)
        )
    )
    members = list(
        (
            await database.execute(
                select(CompanyUser.user_id, User.name)
                .join(User, User.id == CompanyUser.user_id)
                .where(
                    CompanyUser.company_id == company_id,
                    CompanyUser.status == "active",
                    User.status == "active",
                    User.deleted_at.is_(None),
                )
                .order_by(User.name)
            )
        ).all()
    )
    capacities = {
        row.user_id: row
        for row in await database.scalars(
            select(SupportAgentCapacity).where(SupportAgentCapacity.company_id == company_id)
        )
    }
    agent_skills: dict[UUID, list[AgentSkillInput]] = defaultdict(list)
    for agent_skill_row in await database.scalars(
        select(SupportAgentSkill).where(SupportAgentSkill.company_id == company_id)
    ):
        agent_skills[agent_skill_row.user_id].append(
            AgentSkillInput(
                skill_id=agent_skill_row.skill_id,
                proficiency=agent_skill_row.proficiency,
            )
        )
    active_counts = {
        user_id: int(count)
        for user_id, count in (
            await database.execute(
                select(SupportTicket.assignee_user_id, func.count(SupportTicket.id))
                .where(
                    SupportTicket.company_id == company_id,
                    SupportTicket.assignee_user_id.is_not(None),
                    SupportTicket.status.in_(("open", "in_progress", "waiting")),
                )
                .group_by(SupportTicket.assignee_user_id)
            )
        ).all()
        if user_id is not None
    }
    queue_skills: dict[UUID, list[UUID]] = defaultdict(list)
    for queue_skill_row in await database.scalars(
        select(SupportQueueSkill).where(SupportQueueSkill.company_id == company_id)
    ):
        queue_skills[queue_skill_row.queue_id].append(queue_skill_row.skill_id)

    agents: list[SupportRoutingAgentResponse] = []
    for user_id, user_name in members:
        capacity = capacities.get(user_id)
        agents.append(
            SupportRoutingAgentResponse(
                user_id=user_id,
                user_name=user_name,
                status=capacity.status if capacity else "offline",
                queue_id=capacity.queue_id if capacity else None,
                max_active_tickets=capacity.max_active_tickets if capacity else 5,
                active_tickets=active_counts.get(user_id, 0),
                languages=list(capacity.languages) if capacity else [],
                accepted_channels=list(capacity.accepted_channels) if capacity else [],
                skills=sorted(agent_skills[user_id], key=lambda item: str(item.skill_id)),
            )
        )
    return SupportRoutingConfigurationResponse(
        skills=[SupportSkillResponse.model_validate(row) for row in skills],
        agents=agents,
        queues=[
            SupportQueueRoutingResponse(
                queue_id=queue.id,
                queue_name=queue.name,
                required_skill_ids=sorted(queue_skills[queue.id], key=str),
            )
            for queue in queues
        ],
    )


async def create_skill(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    payload: SupportSkillCreate,
) -> SupportSkillResponse:
    row = SupportSkill(
        company_id=company_id,
        created_by_user_id=actor_user_id,
        **payload.model_dump(),
    )
    database.add(row)
    try:
        await database.flush()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(
            status_code=409,
            detail="Já existe uma habilidade com esse identificador.",
        ) from exc
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="support.routing.skill.created",
        target_type="support_skill",
        target_id=row.id,
        details={"key": row.key},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="support.routing.configuration_updated",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="internal",
            payload={"resource": "skill", "resource_id": str(row.id)},
        ),
    )
    await database.commit()
    await database.refresh(row)
    return SupportSkillResponse.model_validate(row)


async def upsert_agent_capacity(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    user_id: UUID,
    payload: SupportAgentCapacityUpsert,
) -> SupportRoutingConfigurationResponse:
    member = await database.scalar(
        select(CompanyUser).where(
            CompanyUser.company_id == company_id,
            CompanyUser.user_id == user_id,
            CompanyUser.status == "active",
        )
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Atendente não encontrado na empresa.")
    if payload.queue_id is not None:
        queue_id = await database.scalar(
            select(SupportQueue.id).where(
                SupportQueue.company_id == company_id,
                SupportQueue.id == payload.queue_id,
                SupportQueue.is_active.is_(True),
            )
        )
        if queue_id is None:
            raise HTTPException(status_code=404, detail="Fila não encontrada.")
    skill_ids = {item.skill_id for item in payload.skills}
    if not await _skill_ids_exist(database, company_id, skill_ids):
        raise HTTPException(status_code=404, detail="Habilidade não encontrada.")

    row = await database.scalar(
        select(SupportAgentCapacity).where(
            SupportAgentCapacity.company_id == company_id,
            SupportAgentCapacity.user_id == user_id,
        )
    )
    values = payload.model_dump(exclude={"skills"})
    if row is None:
        row = SupportAgentCapacity(
            company_id=company_id,
            user_id=user_id,
            updated_by_user_id=actor_user_id,
            **values,
        )
        database.add(row)
    else:
        for field, value in values.items():
            setattr(row, field, value)
        row.updated_by_user_id = actor_user_id
        row.updated_at = utc_now()
    await database.execute(
        delete(SupportAgentSkill).where(
            SupportAgentSkill.company_id == company_id,
            SupportAgentSkill.user_id == user_id,
        )
    )
    database.add_all(
        [
            SupportAgentSkill(
                company_id=company_id,
                user_id=user_id,
                skill_id=item.skill_id,
                proficiency=item.proficiency,
                created_by_user_id=actor_user_id,
            )
            for item in payload.skills
        ]
    )
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="support.routing.agent_configured",
        target_type="user",
        target_id=user_id,
        details={
            "status": payload.status,
            "capacity": payload.max_active_tickets,
            "skill_count": len(payload.skills),
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="support.routing.configuration_updated",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="internal",
            payload={"resource": "agent", "resource_id": str(user_id)},
        ),
    )
    await database.commit()
    return await routing_configuration(database, company_id)


async def update_queue_skills(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    queue_id: UUID,
    payload: SupportQueueSkillsUpdate,
) -> SupportRoutingConfigurationResponse:
    queue = await database.scalar(
        select(SupportQueue).where(
            SupportQueue.company_id == company_id,
            SupportQueue.id == queue_id,
            SupportQueue.is_active.is_(True),
        )
    )
    if queue is None:
        raise HTTPException(status_code=404, detail="Fila não encontrada.")
    skill_ids = set(payload.required_skill_ids)
    if not await _skill_ids_exist(database, company_id, skill_ids):
        raise HTTPException(status_code=404, detail="Habilidade não encontrada.")
    await database.execute(
        delete(SupportQueueSkill).where(
            SupportQueueSkill.company_id == company_id,
            SupportQueueSkill.queue_id == queue_id,
        )
    )
    database.add_all(
        [
            SupportQueueSkill(
                company_id=company_id,
                queue_id=queue_id,
                skill_id=skill_id,
                created_by_user_id=actor_user_id,
            )
            for skill_id in payload.required_skill_ids
        ]
    )
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="support.routing.queue_configured",
        target_type="support_queue",
        target_id=queue_id,
        details={"required_skill_count": len(skill_ids)},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="support.routing.configuration_updated",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="internal",
            payload={"resource": "queue", "resource_id": str(queue_id)},
        ),
    )
    await database.commit()
    return await routing_configuration(database, company_id)


async def recommend_ticket_routing(
    database: AsyncSession,
    *,
    company_id: UUID,
    ticket_id: UUID,
    payload: SupportRoutingRequest,
) -> SupportRoutingRecommendationResponse:
    ticket = await _ticket(database, company_id, ticket_id)
    required_skill_ids: set[UUID] = set()
    if ticket.queue_id is not None:
        required_skill_ids.update(
            await database.scalars(
                select(SupportQueueSkill.skill_id).where(
                    SupportQueueSkill.company_id == company_id,
                    SupportQueueSkill.queue_id == ticket.queue_id,
                )
            )
        )
    selected_skill_id = payload.required_skill_id or ticket.required_skill_id
    if selected_skill_id is not None:
        if not await _skill_ids_exist(database, company_id, {selected_skill_id}):
            raise HTTPException(status_code=404, detail="Habilidade não encontrada.")
        required_skill_ids.add(selected_skill_id)
    language_code = payload.language_code or ticket.language_code
    configuration = await routing_configuration(database, company_id)
    candidates: list[SupportRoutingCandidateResponse] = []
    for agent in configuration.agents:
        skill_levels = {item.skill_id: item.proficiency for item in agent.skills}
        scored = score_routing_candidate(
            RoutingCandidateInput(
                status=agent.status,
                max_active_tickets=agent.max_active_tickets,
                active_tickets=agent.active_tickets,
                primary_queue_matches=bool(
                    ticket.queue_id is not None and agent.queue_id == ticket.queue_id
                ),
                languages=tuple(agent.languages),
                accepted_channels=tuple(agent.accepted_channels),
                skill_levels=skill_levels,
            ),
            channel=ticket.channel,
            language_code=language_code,
            required_skill_ids=tuple(sorted(required_skill_ids, key=str)),
        )
        if scored is None:
            continue
        score, reasons = scored
        proficiency = (
            min(skill_levels[item] for item in required_skill_ids) if required_skill_ids else None
        )
        candidates.append(
            SupportRoutingCandidateResponse(
                user_id=agent.user_id,
                user_name=agent.user_name,
                score=score,
                active_tickets=agent.active_tickets,
                max_active_tickets=agent.max_active_tickets,
                load_percent=round(agent.active_tickets * 100 / agent.max_active_tickets),
                proficiency=proficiency,
                reasons=reasons,
            )
        )
    candidates.sort(key=lambda item: (-item.score, item.active_tickets, item.user_name.lower()))
    explanation = (
        "A ordem considera disponibilidade, habilidades obrigatórias, idioma, "
        "canal, fila e menor carga. Nenhuma atribuição foi executada."
        if candidates
        else "Nenhum atendente disponível atende simultaneamente aos requisitos."
    )
    return SupportRoutingRecommendationResponse(
        ticket_id=ticket.id,
        channel=ticket.channel,
        language_code=language_code,
        required_skill_ids=sorted(required_skill_ids, key=str),
        candidates=candidates,
        explanation=explanation,
    )


async def assign_ticket_routing(
    database: AsyncSession,
    *,
    company_id: UUID,
    actor_user_id: UUID,
    ticket_id: UUID,
    payload: SupportRoutingRequest,
    candidate_user_id: UUID | None,
) -> SupportRoutingAssignmentResponse:
    recommendation = await recommend_ticket_routing(
        database,
        company_id=company_id,
        ticket_id=ticket_id,
        payload=payload,
    )
    candidate = next(
        (
            item
            for item in recommendation.candidates
            if candidate_user_id is None or item.user_id == candidate_user_id
        ),
        None,
    )
    if candidate is None:
        raise HTTPException(
            status_code=409,
            detail="Nenhum atendente elegível está disponível para esta atribuição.",
        )
    ticket = await _ticket(database, company_id, ticket_id)
    ticket.assignee_user_id = candidate.user_id
    ticket.language_code = recommendation.language_code
    ticket.required_skill_id = (
        recommendation.required_skill_ids[0]
        if len(recommendation.required_skill_ids) == 1
        else payload.required_skill_id
    )
    ticket.updated_at = utc_now()
    database.add(
        SupportTicketEvent(
            company_id=company_id,
            ticket_id=ticket.id,
            actor_user_id=actor_user_id,
            event_type="routed",
            description="Chamado atribuído pelo roteamento inteligente.",
            details={
                "assigned_user_id": str(candidate.user_id),
                "score": candidate.score,
                "required_skill_count": len(recommendation.required_skill_ids),
            },
        )
    )
    record_authorization_audit(
        database,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="support.ticket.routed",
        target_type="support_ticket",
        target_id=ticket.id,
        details={
            "assigned_user_id": str(candidate.user_id),
            "score": candidate.score,
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="support.ticket.routed",
            company_id=company_id,
            actor_user_id=actor_user_id,
            classification="confidential",
            payload={
                "ticket_id": str(ticket.id),
                "assigned_user_id": str(candidate.user_id),
            },
        ),
    )
    await database.commit()
    return SupportRoutingAssignmentResponse(
        ticket_id=ticket.id,
        assigned_user_id=candidate.user_id,
        assigned_user_name=candidate.user_name,
        score=candidate.score,
        reasons=candidate.reasons,
    )
