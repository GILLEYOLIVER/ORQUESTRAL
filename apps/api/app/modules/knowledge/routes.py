from __future__ import annotations

import asyncio
import hashlib
from io import BytesIO
from typing import Annotated, Any
from uuid import UUID, uuid4

import httpx
from celery import Celery
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.billing.service import UsageMetric, enforce_limit, record_usage
from app.modules.knowledge.models import KnowledgeBase, KnowledgeDocument
from app.modules.knowledge.processing import search_knowledge, storage, storage_sse
from app.modules.knowledge.schemas import (
    BaseCreate,
    BaseResponse,
    DocumentResponse,
    SearchResult,
    URLImport,
)
from app.modules.knowledge.security import KnowledgeSecurityError, validate_file, validate_web_url

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge"])
CanView = Annotated[Principal, Depends(require_permission("knowledge.view"))]
CanManage = Annotated[Principal, Depends(require_permission("knowledge.manage"))]


async def _base(db: AsyncSession, base_id: UUID, company_id: UUID) -> KnowledgeBase:
    item = await db.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == base_id, KnowledgeBase.company_id == company_id
        )
    )
    if not item:
        raise HTTPException(404, "Base de conhecimento não encontrada.")
    return item


def _enqueue(settings: Settings, doc_id: UUID) -> None:
    if not settings.background_worker_enabled:
        return
    Celery(broker=str(settings.celery_broker_url)).send_task(
        "orkestral.knowledge.process_document", args=[str(doc_id)]
    )


@router.get("", response_model=list[BaseResponse])
async def bases(principal: CanView, db: DatabaseSession) -> list[BaseResponse]:
    context = get_request_context(principal)
    rows = (
        await db.scalars(
            select(KnowledgeBase)
            .where(KnowledgeBase.company_id == context.company_id)
            .order_by(KnowledgeBase.created_at.desc())
        )
    ).all()
    return [BaseResponse.model_validate(x, from_attributes=True) for x in rows]


@router.post("", response_model=BaseResponse, status_code=201)
async def create_base(
    payload: BaseCreate, principal: CanManage, db: DatabaseSession
) -> BaseResponse:
    context = get_request_context(principal)
    item = KnowledgeBase(
        company_id=context.company_id, created_by_user_id=context.user_id, **payload.model_dump()
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return BaseResponse.model_validate(item, from_attributes=True)


@router.get("/{base_id}/documents", response_model=list[DocumentResponse])
async def documents(
    base_id: UUID, principal: CanView, db: DatabaseSession
) -> list[DocumentResponse]:
    context = get_request_context(principal)
    await _base(db, base_id, context.company_id)
    rows = (
        await db.scalars(
            select(KnowledgeDocument)
            .where(
                KnowledgeDocument.knowledge_base_id == base_id,
                KnowledgeDocument.company_id == context.company_id,
            )
            .order_by(KnowledgeDocument.created_at.desc())
        )
    ).all()
    return [DocumentResponse.model_validate(x, from_attributes=True) for x in rows]


async def _store(
    data: bytes,
    name: str,
    mime: str,
    base_id: UUID,
    context: Any,
    db: AsyncSession,
    settings: Settings,
    source_type: str = "upload",
    source_url: str | None = None,
) -> DocumentResponse:
    if not settings.object_storage_enabled:
        raise HTTPException(
            503,
            "Arquivos da base de conhecimento estão indisponíveis no ambiente remoto reduzido.",
        )
    try:
        validate_file(data, mime, settings.knowledge_max_file_bytes)
    except KnowledgeSecurityError as exc:
        raise HTTPException(422, str(exc)) from exc
    await enforce_limit(
        db,
        company_id=context.company_id,
        metric=UsageMetric.DOCUMENTS,
        enforcement_enabled=settings.billing_enforcement_enabled,
    )
    await enforce_limit(
        db,
        company_id=context.company_id,
        metric=UsageMetric.STORAGE_BYTES,
        increment=len(data),
        enforcement_enabled=settings.billing_enforcement_enabled,
    )
    doc_id = uuid4()
    key = f"knowledge/{context.company_id}/{base_id}/{doc_id}/{name}"
    client = storage(settings)
    await asyncio.to_thread(
        lambda: (
            client.bucket_exists(settings.storage_bucket)
            or client.make_bucket(settings.storage_bucket)
        )
    )
    await asyncio.to_thread(
        client.put_object,
        settings.storage_bucket,
        key,
        BytesIO(data),
        len(data),
        content_type=mime,
        sse=storage_sse(settings),
    )
    doc = KnowledgeDocument(
        id=doc_id,
        company_id=context.company_id,
        knowledge_base_id=base_id,
        uploaded_by_user_id=context.user_id,
        name=name[:255],
        source_type=source_type,
        source_url=source_url,
        mime_type=mime,
        size_bytes=len(data),
        storage_key=key,
        checksum_sha256=hashlib.sha256(data).hexdigest(),
    )
    db.add(doc)
    await record_usage(
        db,
        company_id=context.company_id,
        metric=UsageMetric.DOCUMENTS,
        quantity=1,
        metadata={"document_id": str(doc.id), "knowledge_base_id": str(base_id)},
        idempotency_key=f"knowledge-document:{doc.id}",
    )
    await record_usage(
        db,
        company_id=context.company_id,
        metric=UsageMetric.STORAGE_BYTES,
        quantity=len(data),
        metadata={"document_id": str(doc.id), "mime_type": mime},
        idempotency_key=f"knowledge-storage:{doc.id}",
    )
    await db.commit()
    await db.refresh(doc)
    _enqueue(settings, doc.id)
    return DocumentResponse.model_validate(doc, from_attributes=True)


@router.post("/{base_id}/documents", response_model=DocumentResponse, status_code=202)
async def upload(
    base_id: UUID,
    principal: CanManage,
    db: DatabaseSession,
    settings: RequestSettings,
    file: UploadFile = File(...),
) -> DocumentResponse:
    context = get_request_context(principal)
    await _base(db, base_id, context.company_id)
    data = await file.read(settings.knowledge_max_file_bytes + 1)
    return await _store(
        data,
        file.filename or "documento",
        file.content_type or "application/octet-stream",
        base_id,
        context,
        db,
        settings,
    )


@router.post("/{base_id}/web", response_model=DocumentResponse, status_code=202)
async def import_web(
    base_id: UUID,
    payload: URLImport,
    principal: CanManage,
    db: DatabaseSession,
    settings: RequestSettings,
) -> DocumentResponse:
    context = get_request_context(principal)
    await _base(db, base_id, context.company_id)
    try:
        url = validate_web_url(payload.url, settings.knowledge_web_allowed_domains)
    except KnowledgeSecurityError as exc:
        raise HTTPException(422, str(exc)) from exc
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        response = await client.get(url, headers={"User-Agent": "OrkestralKnowledge/1.0"})
    response.raise_for_status()
    return await _store(
        response.content,
        payload.name or url,
        "text/html",
        base_id,
        context,
        db,
        settings,
        "web",
        url,
    )


@router.post(
    "/{base_id}/documents/{document_id}/reprocess", response_model=DocumentResponse, status_code=202
)
async def reprocess(
    base_id: UUID,
    document_id: UUID,
    principal: CanManage,
    db: DatabaseSession,
    settings: RequestSettings,
) -> DocumentResponse:
    context = get_request_context(principal)
    doc = await db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.knowledge_base_id == base_id,
            KnowledgeDocument.company_id == context.company_id,
        )
    )
    if not doc:
        raise HTTPException(404, "Documento não encontrado.")
    doc.status = "uploaded"
    doc.error_summary = None
    await db.commit()
    _enqueue(settings, doc.id)
    return DocumentResponse.model_validate(doc, from_attributes=True)


@router.post("/{base_id}/reindex", response_model=dict[str, int], status_code=202)
async def reindex(
    base_id: UUID, principal: CanManage, db: DatabaseSession, settings: RequestSettings
) -> dict[str, int]:
    context = get_request_context(principal)
    await _base(db, base_id, context.company_id)
    documents = (
        await db.scalars(
            select(KnowledgeDocument).where(
                KnowledgeDocument.knowledge_base_id == base_id,
                KnowledgeDocument.company_id == context.company_id,
            )
        )
    ).all()
    for document in documents:
        document.status = "uploaded"
        document.error_summary = None
        document.processed_at = None
    await db.commit()
    for document in documents:
        _enqueue(settings, document.id)
    return {"queued": len(documents)}


@router.delete("/{base_id}/documents/{document_id}", status_code=204)
async def remove(
    base_id: UUID,
    document_id: UUID,
    principal: CanManage,
    db: DatabaseSession,
    settings: RequestSettings,
) -> None:
    context = get_request_context(principal)
    doc = await db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.knowledge_base_id == base_id,
            KnowledgeDocument.company_id == context.company_id,
        )
    )
    if not doc:
        raise HTTPException(404, "Documento não encontrado.")
    await asyncio.to_thread(
        storage(settings).remove_object, settings.storage_bucket, doc.storage_key
    )
    await db.delete(doc)
    await db.commit()


@router.get("/{base_id}/search", response_model=list[SearchResult])
async def search(
    base_id: UUID,
    principal: CanView,
    db: DatabaseSession,
    settings: RequestSettings,
    q: str = Query(min_length=2, max_length=1000),
    limit: int = Query(5, ge=1, le=20),
) -> list[SearchResult]:
    context = get_request_context(principal)
    await _base(db, base_id, context.company_id)
    return [
        SearchResult.model_validate(x)
        for x in await search_knowledge(
            db,
            settings=settings,
            company_id=context.company_id,
            base_id=base_id,
            query=q,
            limit=limit,
        )
    ]
