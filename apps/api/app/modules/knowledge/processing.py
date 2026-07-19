from __future__ import annotations

import asyncio
import hashlib
import re
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urlsplit
from uuid import UUID

from docx import Document
from minio import Minio
from openpyxl import load_workbook  # type: ignore[import-untyped]
from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.database import create_database_engine
from app.core.security import utc_now
from app.modules.knowledge.embeddings import (
    get_embedding_provider,
    local_hash_embedding,
)
from app.modules.knowledge.models import KnowledgeChunk, KnowledgeDocument


class _HTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        self.skip += tag in {"script", "style", "nav"}

    def handle_endtag(self, tag: str) -> None:
        self.skip = max(0, self.skip - (tag in {"script", "style", "nav"}))

    def handle_data(self, data: str) -> None:
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def storage(settings: Settings) -> Minio:
    endpoint = urlsplit(str(settings.storage_endpoint))
    return Minio(
        endpoint.netloc,
        access_key=settings.storage_access_key,
        secret_key=settings.storage_secret_key,
        secure=endpoint.scheme == "https",
    )


def extract(data: bytes, mime: str) -> str:
    if mime == "application/pdf":
        return "\n".join(
            (page.extract_text() or "") for page in PdfReader(BytesIO(data)).pages
        )
    if mime.endswith("wordprocessingml.document"):
        return "\n".join(paragraph.text for paragraph in Document(BytesIO(data)).paragraphs)
    if mime.endswith("spreadsheetml.sheet"):
        book = load_workbook(BytesIO(data), read_only=True, data_only=True)
        return "\n".join(
            " | ".join(str(value) for value in row if value is not None)
            for sheet in book.worksheets
            for row in sheet.iter_rows(values_only=True)
        )
    text = data.decode("utf-8", errors="replace")
    if mime == "text/html":
        parser = _HTML()
        parser.feed(text)
        return "\n".join(parser.parts)
    return text


def chunks(text: str, size: int = 1200, overlap: int = 150) -> list[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    result: list[str] = []
    start = 0
    while start < len(clean):
        result.append(clean[start : start + size])
        start += size - overlap
    return [item for item in result if item.strip()]


def embed(text: str, dimensions: int = 384) -> list[float]:
    """Compatibilidade local explícita; produção usa o provedor configurado."""
    return local_hash_embedding(text, dimensions)


async def process_document(document_id: UUID, settings: Settings) -> None:
    engine = create_database_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as database:
            document = await database.scalar(
                select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
            )
            if document is None:
                return
            document.status = "processing"
            document.error_summary = None
            await database.commit()
            try:
                client = storage(settings)
                response = await asyncio.to_thread(
                    client.get_object, settings.storage_bucket, document.storage_key
                )
                try:
                    data = await asyncio.to_thread(response.read)
                finally:
                    response.close()
                    response.release_conn()
                text = extract(data, document.mime_type)
                parts = chunks(text)
                if not parts:
                    raise ValueError("Nenhum texto útil foi extraído.")
                provider = get_embedding_provider(settings)
                vectors = await provider.embed_many(parts)
                await database.execute(
                    delete(KnowledgeChunk).where(
                        KnowledgeChunk.document_id == document.id
                    )
                )
                for index, (part, vector) in enumerate(zip(parts, vectors, strict=True)):
                    checksum = hashlib.sha256(part.encode()).hexdigest()[:16]
                    database.add(
                        KnowledgeChunk(
                            company_id=document.company_id,
                            knowledge_base_id=document.knowledge_base_id,
                            document_id=document.id,
                            chunk_index=index,
                            content=part,
                            token_count=max(1, len(part) // 4),
                            embedding_ref=f"{provider.reference}:{checksum}"[:120],
                            embedding=vector,
                            chunk_metadata={"document_name": document.name},
                        )
                    )
                document.status = "ready"
                document.processed_at = utc_now()
                document.document_metadata = {
                    **document.document_metadata,
                    "chunk_count": len(parts),
                    "embedding_provider": settings.knowledge_embedding_provider,
                    "embedding_model": provider.reference,
                    "embedding_dimensions": settings.knowledge_embedding_dimensions,
                }
            except Exception as exc:
                document.status = "error"
                document.error_summary = str(exc)[:1000]
            await database.commit()
    finally:
        await engine.dispose()


def process_document_sync(document_id: str) -> None:
    asyncio.run(process_document(UUID(document_id), get_settings()))


async def search_knowledge(
    database: AsyncSession,
    *,
    settings: Settings,
    company_id: UUID,
    base_id: UUID,
    query: str,
    limit: int = 5,
) -> list[dict[str, object]]:
    provider = get_embedding_provider(settings)
    target = (await provider.embed_many([query]))[0]
    distance = KnowledgeChunk.embedding.cosine_distance(target).label("distance")
    rows = (
        await database.execute(
            select(KnowledgeChunk, distance)
            .join(
                KnowledgeDocument,
                KnowledgeDocument.id == KnowledgeChunk.document_id,
            )
            .where(
                KnowledgeChunk.company_id == company_id,
                KnowledgeChunk.knowledge_base_id == base_id,
                KnowledgeDocument.company_id == company_id,
                KnowledgeDocument.status == "ready",
            )
            .order_by(distance)
            .limit(limit)
        )
    ).all()
    return [
        {
            "chunk_id": str(row.id),
            "document_id": str(row.document_id),
            "document_name": row.chunk_metadata.get("document_name", "Documento"),
            "chunk_index": row.chunk_index,
            "content": row.content,
            "score": round(max(-1.0, min(1.0, 1.0 - float(raw_distance))), 4),
        }
        for row, raw_distance in rows
        if raw_distance is not None and 1.0 - float(raw_distance) > 0
    ]
