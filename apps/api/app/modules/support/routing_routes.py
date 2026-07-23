from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.dependencies import DatabaseSession
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.modularity.dependencies import require_active_module
from app.modules.support.routing_schemas import (
    SupportAgentCapacityUpsert,
    SupportQueueSkillsUpdate,
    SupportRoutingAssignmentResponse,
    SupportRoutingAssignRequest,
    SupportRoutingConfigurationResponse,
    SupportRoutingRecommendationResponse,
    SupportRoutingRequest,
    SupportSkillCreate,
    SupportSkillResponse,
)
from app.modules.support.routing_service import (
    assign_ticket_routing,
    create_skill,
    recommend_ticket_routing,
    routing_configuration,
    update_queue_skills,
    upsert_agent_capacity,
)

router = APIRouter(prefix="/support/routing", tags=["support-routing"])

ActiveSupport = Annotated[Principal, Depends(require_active_module("support"))]
CanViewTickets = Annotated[
    Principal,
    Depends(require_permission("support.tickets.view")),
]
CanUpdateTickets = Annotated[
    Principal,
    Depends(require_permission("support.tickets.update")),
]


@router.get("/configuration", response_model=SupportRoutingConfigurationResponse)
async def get_routing_configuration(
    principal: CanViewTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportRoutingConfigurationResponse:
    context = get_request_context(principal)
    return await routing_configuration(database, context.company_id)


@router.post("/skills", response_model=SupportSkillResponse, status_code=201)
async def post_routing_skill(
    payload: SupportSkillCreate,
    principal: CanUpdateTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportSkillResponse:
    context = get_request_context(principal)
    return await create_skill(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        payload=payload,
    )


@router.put("/agents/{user_id}", response_model=SupportRoutingConfigurationResponse)
async def put_routing_agent(
    user_id: UUID,
    payload: SupportAgentCapacityUpsert,
    principal: CanUpdateTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportRoutingConfigurationResponse:
    context = get_request_context(principal)
    return await upsert_agent_capacity(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        user_id=user_id,
        payload=payload,
    )


@router.put("/queues/{queue_id}", response_model=SupportRoutingConfigurationResponse)
async def put_routing_queue(
    queue_id: UUID,
    payload: SupportQueueSkillsUpdate,
    principal: CanUpdateTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportRoutingConfigurationResponse:
    context = get_request_context(principal)
    return await update_queue_skills(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        queue_id=queue_id,
        payload=payload,
    )


@router.post(
    "/tickets/{ticket_id}/recommend",
    response_model=SupportRoutingRecommendationResponse,
)
async def post_ticket_routing_recommendation(
    ticket_id: UUID,
    payload: SupportRoutingRequest,
    principal: CanViewTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportRoutingRecommendationResponse:
    context = get_request_context(principal)
    return await recommend_ticket_routing(
        database,
        company_id=context.company_id,
        ticket_id=ticket_id,
        payload=payload,
    )


@router.post(
    "/tickets/{ticket_id}/assign",
    response_model=SupportRoutingAssignmentResponse,
)
async def post_ticket_routing_assignment(
    ticket_id: UUID,
    payload: SupportRoutingAssignRequest,
    principal: CanUpdateTickets,
    _: ActiveSupport,
    database: DatabaseSession,
) -> SupportRoutingAssignmentResponse:
    context = get_request_context(principal)
    return await assign_ticket_routing(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        ticket_id=ticket_id,
        payload=SupportRoutingRequest(
            language_code=payload.language_code,
            required_skill_id=payload.required_skill_id,
        ),
        candidate_user_id=payload.candidate_user_id,
    )
