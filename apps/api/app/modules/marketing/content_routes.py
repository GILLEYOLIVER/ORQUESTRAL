from __future__ import annotations

import hashlib
import hmac
from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select

from app.core.database import apply_tenant_database_context
from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.marketing.content_models import (
    MarketingChannelConnector,
    MarketingContent,
    MarketingContentVersion,
    MarketingFormSubmission,
    MarketingLandingPage,
    MarketingPublicPageRegistry,
)
from app.modules.marketing.content_schemas import (
    ChannelConnectorResponse,
    ChannelConnectorUpsert,
    ContentCreate,
    ContentResponse,
    ContentReview,
    ContentVersionCreate,
    LandingPageCreate,
    LandingPageResponse,
    PublicFormSubmission,
    PublicFormSubmissionResponse,
    PublicLandingPageResponse,
)
from app.modules.modularity.dependencies import require_active_module
from app.modules.plugins.models import IntegrationCredential

router = APIRouter(
    prefix="/marketing/content",
    tags=["marketing-content"],
    dependencies=[Depends(require_active_module("marketing"))],
)
public_router = APIRouter(prefix="/public/marketing", tags=["public-marketing"])
CanView = Annotated[Principal, Depends(require_permission("marketing.view"))]
CanManage = Annotated[Principal, Depends(require_permission("marketing.content.manage"))]


def _connector_response(row: MarketingChannelConnector) -> ChannelConnectorResponse:
    return ChannelConnectorResponse.model_validate(row, from_attributes=True)


async def _content_response(
    database: DatabaseSession, row: MarketingContent
) -> ContentResponse:
    version = await database.scalar(
        select(MarketingContentVersion).where(
            MarketingContentVersion.company_id == row.company_id,
            MarketingContentVersion.content_id == row.id,
            MarketingContentVersion.version == row.current_version,
        )
    )
    if version is None:
        raise HTTPException(status_code=500, detail="Versão atual do conteúdo não encontrada.")
    return ContentResponse(
        id=row.id,
        name=row.name,
        kind=row.kind,
        status=row.status,
        current_version=row.current_version,
        subject=version.subject,
        body=version.body,
        ai_generated=version.ai_generated,
        review_status=version.review_status,
        updated_at=row.updated_at,
    )


@router.get("/connectors", response_model=list[ChannelConnectorResponse])
async def list_connectors(
    principal: CanView, database: DatabaseSession
) -> list[ChannelConnectorResponse]:
    context = get_request_context(principal)
    rows = (
        await database.scalars(
            select(MarketingChannelConnector)
            .where(MarketingChannelConnector.company_id == context.company_id)
            .order_by(MarketingChannelConnector.channel, MarketingChannelConnector.provider)
        )
    ).all()
    return [_connector_response(row) for row in rows]


@router.put("/connectors/{channel}/{provider}", response_model=ChannelConnectorResponse)
async def upsert_connector(
    channel: str,
    provider: str,
    payload: ChannelConnectorUpsert,
    principal: CanManage,
    database: DatabaseSession,
) -> ChannelConnectorResponse:
    context = get_request_context(principal)
    if channel != payload.channel or provider != payload.provider:
        raise HTTPException(status_code=422, detail="Canal e provedor devem corresponder à rota.")
    if payload.status == "active":
        if payload.credential_id is None:
            raise HTTPException(status_code=422, detail="Conector ativo exige credencial.")
        valid_credential = await database.scalar(
            select(func.count(IntegrationCredential.id)).where(
                IntegrationCredential.id == payload.credential_id,
                IntegrationCredential.company_id == context.company_id,
                IntegrationCredential.status == "active",
            )
        )
        if not valid_credential:
            raise HTTPException(status_code=422, detail="Credencial ativa não encontrada nesta empresa.")
    forbidden = {"token", "secret", "password", "api_key", "authorization"}
    if forbidden.intersection(key.lower() for key in payload.configuration):
        raise HTTPException(status_code=422, detail="Segredos devem permanecer no cofre de credenciais.")
    row = await database.scalar(
        select(MarketingChannelConnector).where(
            MarketingChannelConnector.company_id == context.company_id,
            MarketingChannelConnector.channel == channel,
            MarketingChannelConnector.provider == provider,
        )
    )
    if row is None:
        row = MarketingChannelConnector(
            company_id=context.company_id,
            created_by_user_id=context.user_id,
            **payload.model_dump(),
        )
        database.add(row)
    else:
        for key, value in payload.model_dump().items():
            setattr(row, key, value)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="marketing.channel_connector.updated",
        target_type="marketing_channel_connector",
        target_id=row.id,
        details={"channel": row.channel, "provider": row.provider, "status": row.status},
    )
    await database.commit()
    await database.refresh(row)
    return _connector_response(row)


@router.get("", response_model=list[ContentResponse])
async def list_contents(
    principal: CanView, database: DatabaseSession
) -> list[ContentResponse]:
    context = get_request_context(principal)
    rows = (
        await database.scalars(
            select(MarketingContent)
            .where(
                MarketingContent.company_id == context.company_id,
                MarketingContent.status != "archived",
            )
            .order_by(MarketingContent.updated_at.desc())
        )
    ).all()
    return [await _content_response(database, row) for row in rows]


@router.post("", response_model=ContentResponse, status_code=status.HTTP_201_CREATED)
async def create_content(
    payload: ContentCreate, principal: CanManage, database: DatabaseSession
) -> ContentResponse:
    context = get_request_context(principal)
    row = MarketingContent(
        company_id=context.company_id,
        name=payload.name.strip(),
        kind=payload.kind,
        created_by_user_id=context.user_id,
    )
    database.add(row)
    await database.flush()
    database.add(
        MarketingContentVersion(
            company_id=context.company_id,
            content_id=row.id,
            version=1,
            subject=payload.subject,
            body=payload.body,
            ai_generated=payload.ai_generated,
            created_by_user_id=context.user_id,
        )
    )
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="marketing.content.created",
        target_type="marketing_content",
        target_id=row.id,
        details={"kind": row.kind, "ai_generated": payload.ai_generated},
    )
    await database.commit()
    await database.refresh(row)
    return await _content_response(database, row)


@router.post("/{content_id}/versions", response_model=ContentResponse)
async def create_content_version(
    content_id: UUID,
    payload: ContentVersionCreate,
    principal: CanManage,
    database: DatabaseSession,
) -> ContentResponse:
    context = get_request_context(principal)
    row = await database.scalar(
        select(MarketingContent).where(
            MarketingContent.id == content_id,
            MarketingContent.company_id == context.company_id,
            MarketingContent.status != "archived",
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Conteúdo não encontrado.")
    row.current_version += 1
    row.status = "draft"
    row.approved_at = None
    row.approved_by_user_id = None
    database.add(
        MarketingContentVersion(
            company_id=context.company_id,
            content_id=row.id,
            version=row.current_version,
            created_by_user_id=context.user_id,
            **payload.model_dump(),
        )
    )
    await database.commit()
    return await _content_response(database, row)


@router.post("/{content_id}/review", response_model=ContentResponse)
async def review_content(
    content_id: UUID,
    payload: ContentReview,
    principal: CanManage,
    database: DatabaseSession,
) -> ContentResponse:
    context = get_request_context(principal)
    row = await database.scalar(
        select(MarketingContent).where(
            MarketingContent.id == content_id,
            MarketingContent.company_id == context.company_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Conteúdo não encontrado.")
    version = await database.scalar(
        select(MarketingContentVersion).where(
            MarketingContentVersion.content_id == row.id,
            MarketingContentVersion.company_id == context.company_id,
            MarketingContentVersion.version == row.current_version,
        )
    )
    if version is None:
        raise HTTPException(status_code=500, detail="Versão atual ausente.")
    if payload.decision == "submit":
        version.review_status = "pending"
        row.status = "in_review"
    else:
        if version.review_status != "pending":
            raise HTTPException(status_code=409, detail="Submeta o conteúdo antes da decisão.")
        if version.created_by_user_id == context.user_id:
            raise HTTPException(status_code=403, detail="O autor não pode aprovar a própria versão.")
        version.review_status = "approved" if payload.decision == "approve" else "rejected"
        version.review_notes = payload.notes
        version.reviewed_by_user_id = context.user_id
        version.reviewed_at = utc_now()
        row.status = "approved" if payload.decision == "approve" else "draft"
        if payload.decision == "approve":
            row.approved_by_user_id = context.user_id
            row.approved_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action=f"marketing.content.{payload.decision}",
        target_type="marketing_content",
        target_id=row.id,
        details={"version": row.current_version},
    )
    await database.commit()
    return await _content_response(database, row)


def _landing_response(row: MarketingLandingPage) -> LandingPageResponse:
    return LandingPageResponse(
        id=row.id,
        public_id=row.public_id,
        content_id=row.content_id,
        slug=row.slug,
        title=row.title,
        status=row.status,
        form_schema=row.form_schema,
        public_path=f"/api/public/marketing/pages/{row.public_id}",
        updated_at=row.updated_at,
    )


@router.get("/pages", response_model=list[LandingPageResponse])
async def list_pages(
    principal: CanView, database: DatabaseSession
) -> list[LandingPageResponse]:
    context = get_request_context(principal)
    rows = (
        await database.scalars(
            select(MarketingLandingPage)
            .where(
                MarketingLandingPage.company_id == context.company_id,
                MarketingLandingPage.status != "archived",
            )
            .order_by(MarketingLandingPage.updated_at.desc())
        )
    ).all()
    return [_landing_response(row) for row in rows]


@router.post("/pages", response_model=LandingPageResponse, status_code=status.HTTP_201_CREATED)
async def create_page(
    payload: LandingPageCreate, principal: CanManage, database: DatabaseSession
) -> LandingPageResponse:
    context = get_request_context(principal)
    content = await database.scalar(
        select(MarketingContent).where(
            MarketingContent.id == payload.content_id,
            MarketingContent.company_id == context.company_id,
            MarketingContent.kind == "landing_page",
            MarketingContent.status == "approved",
        )
    )
    if content is None:
        raise HTTPException(status_code=422, detail="Use conteúdo de landing page aprovado.")
    row = MarketingLandingPage(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    database.add(row)
    await database.flush()
    database.add(
        MarketingPublicPageRegistry(
            public_id=row.public_id,
            company_id=context.company_id,
            page_id=row.id,
        )
    )
    await database.commit()
    await database.refresh(row)
    return _landing_response(row)


@router.post("/pages/{page_id}/publish", response_model=LandingPageResponse)
async def publish_page(
    page_id: UUID, principal: CanManage, database: DatabaseSession
) -> LandingPageResponse:
    context = get_request_context(principal)
    row = await database.scalar(
        select(MarketingLandingPage).where(
            MarketingLandingPage.id == page_id,
            MarketingLandingPage.company_id == context.company_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Landing page não encontrada.")
    row.status = "published"
    row.published_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="marketing.landing_page.published",
        target_type="marketing_landing_page",
        target_id=row.id,
        details={"public_id": str(row.public_id)},
    )
    await database.commit()
    return _landing_response(row)


async def _public_page(
    public_id: UUID, database: DatabaseSession
) -> tuple[MarketingLandingPage, MarketingContentVersion]:
    registry = await database.scalar(
        select(MarketingPublicPageRegistry).where(
            MarketingPublicPageRegistry.public_id == public_id
        )
    )
    if registry is None:
        raise HTTPException(status_code=404, detail="Página não encontrada.")
    await apply_tenant_database_context(
        database, company_id=registry.company_id, access_mode="standard"
    )
    page = await database.scalar(
        select(MarketingLandingPage).where(
            MarketingLandingPage.id == registry.page_id,
            MarketingLandingPage.company_id == registry.company_id,
            MarketingLandingPage.status == "published",
        )
    )
    if page is None:
        raise HTTPException(status_code=404, detail="Página indisponível.")
    content = await database.scalar(
        select(MarketingContent).where(
            MarketingContent.id == page.content_id,
            MarketingContent.company_id == registry.company_id,
            MarketingContent.status == "approved",
        )
    )
    if content is None:
        raise HTTPException(status_code=404, detail="Conteúdo indisponível.")
    version = await database.scalar(
        select(MarketingContentVersion).where(
            MarketingContentVersion.content_id == content.id,
            MarketingContentVersion.company_id == registry.company_id,
            MarketingContentVersion.version == content.current_version,
            MarketingContentVersion.review_status == "approved",
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Versão publicada indisponível.")
    return page, version


@public_router.get("/pages/{public_id}", response_model=PublicLandingPageResponse)
async def get_public_page(
    public_id: UUID, database: DatabaseSession
) -> PublicLandingPageResponse:
    page, version = await _public_page(public_id, database)
    return PublicLandingPageResponse(
        title=page.title,
        body=version.body,
        form_schema=page.form_schema,
    )


def _validated_values(schema: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in schema.get("fields", []):
        name = field["name"]
        value = values.get(name)
        if field.get("required") and (value is None or value == ""):
            raise HTTPException(status_code=422, detail=f"Campo obrigatório ausente: {name}.")
        if value is not None:
            if not isinstance(value, (str, bool)):
                raise HTTPException(status_code=422, detail=f"Valor inválido para {name}.")
            if isinstance(value, str) and len(value) > 5_000:
                raise HTTPException(status_code=422, detail=f"Valor muito longo para {name}.")
            result[name] = value
    return result


@public_router.post(
    "/pages/{public_id}/submit",
    response_model=PublicFormSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_public_form(
    public_id: UUID,
    payload: PublicFormSubmission,
    request: Request,
    settings: RequestSettings,
    database: DatabaseSession,
) -> PublicFormSubmissionResponse:
    page, _ = await _public_page(public_id, database)
    if not payload.consent_granted:
        raise HTTPException(status_code=422, detail="Consentimento obrigatório.")
    values = _validated_values(page.form_schema, payload.values)
    source = request.client.host if request.client else "unknown"
    fingerprint = hmac.new(
        settings.jwt_secret.encode(),
        f"{public_id}:{source}".encode(),
        hashlib.sha256,
    ).hexdigest()
    recent = int(
        await database.scalar(
            select(func.count(MarketingFormSubmission.id)).where(
                MarketingFormSubmission.company_id == page.company_id,
                MarketingFormSubmission.page_id == page.id,
                MarketingFormSubmission.source_fingerprint == fingerprint,
                MarketingFormSubmission.created_at >= utc_now() - timedelta(hours=1),
            )
        )
        or 0
    )
    if recent >= 10:
        raise HTTPException(status_code=429, detail="Limite temporário de envios atingido.")
    submission = MarketingFormSubmission(
        company_id=page.company_id,
        page_id=page.id,
        payload=values,
        consent_granted=True,
        source_fingerprint=fingerprint,
        status="accepted",
    )
    database.add(submission)
    await database.commit()
    return PublicFormSubmissionResponse(submission_id=submission.id, status="accepted")
