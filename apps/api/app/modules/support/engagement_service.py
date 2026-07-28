from __future__ import annotations

import hashlib
from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.models import KnowledgeBase, KnowledgeChunk, KnowledgeDocument
from app.modules.support.engagement_models import (
    SupportResponseCitation,
    SupportSatisfactionSurvey,
)
from app.modules.support.engagement_schemas import (
    SupportKnowledgeCitationInput,
    SupportKnowledgeCitationResponse,
    SupportSatisfactionSummary,
)


def protected_digest(value: str | None) -> str | None:
    normalized = value.strip() if value else ""
    return hashlib.sha256(normalized.encode()).hexdigest() if normalized else None


def satisfaction_summary(rows: list[tuple[int, int, int]]) -> SupportSatisfactionSummary:
    if not rows:
        return SupportSatisfactionSummary(
            responses=0,
            overall_average=0,
            resolution_average=0,
            effort_average=0,
            promoters=0,
            detractors=0,
        )
    count = len(rows)
    return SupportSatisfactionSummary(
        responses=count,
        overall_average=round(sum(row[0] for row in rows) / count, 2),
        resolution_average=round(sum(row[1] for row in rows) / count, 2),
        effort_average=round(sum(row[2] for row in rows) / count, 2),
        promoters=sum(row[0] >= 4 for row in rows),
        detractors=sum(row[0] <= 2 for row in rows),
    )


async def search_support_knowledge(
    database: AsyncSession, *, company_id: UUID, query: str, limit: int
) -> list[SupportKnowledgeCitationResponse]:
    terms = [term for term in query.strip().split() if len(term) >= 2][:6]
    if not terms:
        return []
    rank = sum(
        (case((KnowledgeChunk.content.ilike(f"%{term}%"), 1), else_=0) for term in terms),
        start=case((KnowledgeChunk.id.is_(None), 0), else_=0),
    )
    rows = (
        await database.execute(
            select(KnowledgeChunk, KnowledgeDocument.name, rank.label("rank"))
            .join(
                KnowledgeDocument,
                (KnowledgeDocument.id == KnowledgeChunk.document_id)
                & (KnowledgeDocument.company_id == company_id),
            )
            .join(
                KnowledgeBase,
                (KnowledgeBase.id == KnowledgeChunk.knowledge_base_id)
                & (KnowledgeBase.company_id == company_id),
            )
            .where(
                KnowledgeChunk.company_id == company_id,
                KnowledgeDocument.status == "ready",
                KnowledgeBase.status == "active",
                rank > 0,
            )
            .order_by(rank.desc(), KnowledgeChunk.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        SupportKnowledgeCitationResponse(
            knowledge_base_id=chunk.knowledge_base_id,
            knowledge_document_id=chunk.document_id,
            knowledge_chunk_id=chunk.id,
            document_name=document_name,
            chunk_index=chunk.chunk_index,
            excerpt=chunk.content[:500],
            score=round(float(score) / len(terms), 4),
        )
        for chunk, document_name, score in rows
    ]


async def validated_citations(
    database: AsyncSession,
    *,
    company_id: UUID,
    citations: list[SupportKnowledgeCitationInput],
) -> list[KnowledgeChunk]:
    if not citations:
        return []
    ids = [item.knowledge_chunk_id for item in citations]
    chunks = list(
        await database.scalars(
            select(KnowledgeChunk).where(
                KnowledgeChunk.company_id == company_id,
                KnowledgeChunk.id.in_(ids),
            )
        )
    )
    by_id = {item.id: item for item in chunks}
    if len(by_id) != len(ids):
        raise ValueError("Uma ou mais fontes não pertencem a esta empresa.")
    for citation in citations:
        chunk = by_id[citation.knowledge_chunk_id]
        if (
            chunk.knowledge_base_id != citation.knowledge_base_id
            or chunk.document_id != citation.knowledge_document_id
        ):
            raise ValueError("A referência de conhecimento é inválida.")
    return [by_id[item_id] for item_id in ids]


async def satisfaction_summary_for_company(
    database: AsyncSession, company_id: UUID
) -> SupportSatisfactionSummary:
    result = await database.execute(
        select(
            SupportSatisfactionSurvey.overall_score,
            SupportSatisfactionSurvey.resolution_score,
            SupportSatisfactionSurvey.effort_score,
        ).where(SupportSatisfactionSurvey.company_id == company_id)
    )
    rows = [(overall, resolution, effort) for overall, resolution, effort in result]
    return satisfaction_summary(rows)


def citation_model(
    *,
    company_id: UUID,
    ticket_id: UUID,
    interaction_id: UUID,
    user_id: UUID,
    chunk: KnowledgeChunk,
) -> SupportResponseCitation:
    return SupportResponseCitation(
        company_id=company_id,
        ticket_id=ticket_id,
        interaction_id=interaction_id,
        knowledge_base_id=chunk.knowledge_base_id,
        knowledge_document_id=chunk.document_id,
        knowledge_chunk_id=chunk.id,
        created_by_user_id=user_id,
        excerpt_sha256=protected_digest(chunk.content) or "",
    )
