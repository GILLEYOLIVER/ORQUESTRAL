from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.developer.models import ArtifactPromotion, DeveloperSandbox
from app.modules.developer.schemas import (
    PromotionCreate,
    PromotionDecision,
    PromotionResponse,
    SandboxCreate,
    SandboxResponse,
)
from app.modules.developer.service import can_promote
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event

router = APIRouter(prefix="/developer", tags=["developer-platform"])
CanView = Annotated[Principal, Depends(require_permission("developer.view"))]
CanManage = Annotated[Principal, Depends(require_permission("developer.manage"))]
CanPromote = Annotated[Principal, Depends(require_permission("developer.promote"))]


@router.get("/sandboxes", response_model=list[SandboxResponse])
async def list_sandboxes(
    principal: CanView, database: DatabaseSession
) -> list[SandboxResponse]:
    context = get_request_context(principal)
    rows = await database.scalars(
        select(DeveloperSandbox)
        .where(DeveloperSandbox.company_id == context.company_id)
        .order_by(DeveloperSandbox.created_at.desc())
    )
    return [SandboxResponse.model_validate(row) for row in rows]


@router.post("/sandboxes", response_model=SandboxResponse, status_code=201)
async def create_sandbox(
    payload: SandboxCreate,
    principal: CanManage,
    database: DatabaseSession,
) -> SandboxResponse:
    context = get_request_context(principal)
    if payload.expires_at <= utc_now():
        raise HTTPException(status_code=422, detail="A expiração deve estar no futuro.")
    sandbox = DeveloperSandbox(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    database.add(sandbox)
    try:
        await database.flush()
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="Código de sandbox já utilizado.") from error
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="developer.sandbox.created",
        target_type="developer_sandbox",
        target_id=sandbox.id,
        details={
            "environment": sandbox.environment,
            "data_policy": sandbox.data_policy,
            "expires_at": sandbox.expires_at.isoformat(),
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="developer.sandbox.created",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="internal",
            payload={
                "sandbox_id": str(sandbox.id),
                "environment": sandbox.environment,
                "data_policy": sandbox.data_policy,
            },
        ),
    )
    await database.commit()
    await database.refresh(sandbox)
    return SandboxResponse.model_validate(sandbox)


@router.post("/sandboxes/{sandbox_id}/archive", response_model=SandboxResponse)
async def archive_sandbox(
    sandbox_id: UUID,
    principal: CanManage,
    database: DatabaseSession,
) -> SandboxResponse:
    context = get_request_context(principal)
    sandbox = await database.scalar(
        select(DeveloperSandbox).where(
            DeveloperSandbox.id == sandbox_id,
            DeveloperSandbox.company_id == context.company_id,
        )
    )
    if sandbox is None:
        raise HTTPException(status_code=404, detail="Sandbox não encontrado.")
    sandbox.status = "archived"
    sandbox.archived_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="developer.sandbox.archived",
        target_type="developer_sandbox",
        target_id=sandbox.id,
    )
    await database.commit()
    await database.refresh(sandbox)
    return SandboxResponse.model_validate(sandbox)


@router.get("/promotions", response_model=list[PromotionResponse])
async def list_promotions(
    principal: CanView, database: DatabaseSession
) -> list[PromotionResponse]:
    context = get_request_context(principal)
    rows = await database.scalars(
        select(ArtifactPromotion)
        .where(ArtifactPromotion.company_id == context.company_id)
        .order_by(ArtifactPromotion.requested_at.desc())
    )
    return [PromotionResponse.model_validate(row) for row in rows]


@router.post("/promotions", response_model=PromotionResponse, status_code=201)
async def request_promotion(
    payload: PromotionCreate,
    principal: CanManage,
    database: DatabaseSession,
) -> PromotionResponse:
    context = get_request_context(principal)
    if not can_promote(payload.source_environment, payload.target_environment):
        raise HTTPException(status_code=422, detail="Rota de promoção não permitida.")
    promotion = ArtifactPromotion(
        company_id=context.company_id,
        requested_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    database.add(promotion)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="developer.promotion.requested",
        target_type="artifact_promotion",
        target_id=promotion.id,
        details={
            "artifact_type": promotion.artifact_type,
            "source": promotion.source_environment,
            "target": promotion.target_environment,
            "checksum": promotion.checksum,
        },
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type="developer.promotion.requested",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="internal",
            payload={
                "promotion_id": str(promotion.id),
                "artifact_type": promotion.artifact_type,
                "source": promotion.source_environment,
                "target": promotion.target_environment,
                "checksum": promotion.checksum,
            },
        ),
    )
    await database.commit()
    await database.refresh(promotion)
    return PromotionResponse.model_validate(promotion)


@router.post("/promotions/{promotion_id}/decision", response_model=PromotionResponse)
async def decide_promotion(
    promotion_id: UUID,
    payload: PromotionDecision,
    principal: CanPromote,
    database: DatabaseSession,
) -> PromotionResponse:
    context = get_request_context(principal)
    promotion = await database.scalar(
        select(ArtifactPromotion).where(
            ArtifactPromotion.id == promotion_id,
            ArtifactPromotion.company_id == context.company_id,
        )
    )
    if promotion is None:
        raise HTTPException(status_code=404, detail="Promoção não encontrada.")
    if promotion.status != "requested":
        raise HTTPException(status_code=409, detail="Promoção já decidida.")
    if promotion.requested_by_user_id == context.user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O solicitante não pode aprovar a própria promoção.",
        )
    promotion.status = payload.decision
    promotion.reviewed_by_user_id = context.user_id
    promotion.reviewed_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action=f"developer.promotion.{payload.decision}",
        target_type="artifact_promotion",
        target_id=promotion.id,
        details={"checksum": promotion.checksum},
    )
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=f"developer.promotion.{payload.decision}",
            company_id=context.company_id,
            actor_user_id=context.user_id,
            classification="internal",
            payload={
                "promotion_id": str(promotion.id),
                "artifact_type": promotion.artifact_type,
                "checksum": promotion.checksum,
            },
        ),
    )
    await database.commit()
    await database.refresh(promotion)
    return PromotionResponse.model_validate(promotion)
