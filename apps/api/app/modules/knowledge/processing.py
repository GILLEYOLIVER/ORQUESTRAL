from __future__ import annotations
import asyncio, hashlib, math, re
from html.parser import HTMLParser
from io import BytesIO
from uuid import UUID
from urllib.parse import urlsplit
from docx import Document
from minio import Minio
from openpyxl import load_workbook
from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.config import Settings, get_settings
from app.core.security import utc_now
from app.modules.knowledge.models import KnowledgeChunk, KnowledgeDocument


class _HTML(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs): self.skip += tag in {"script","style","nav"}
    def handle_endtag(self, tag): self.skip = max(0,self.skip-(tag in {"script","style","nav"}))
    def handle_data(self, data):
        if not self.skip and data.strip(): self.parts.append(data.strip())


def storage(settings: Settings) -> Minio:
    endpoint=urlsplit(str(settings.storage_endpoint)); return Minio(endpoint.netloc, access_key=settings.storage_access_key, secret_key=settings.storage_secret_key, secure=endpoint.scheme=="https")


def extract(data: bytes, mime: str) -> str:
    if mime=="application/pdf": return "\n".join((page.extract_text() or "") for page in PdfReader(BytesIO(data)).pages)
    if mime.endswith("wordprocessingml.document"): return "\n".join(p.text for p in Document(BytesIO(data)).paragraphs)
    if mime.endswith("spreadsheetml.sheet"):
        book=load_workbook(BytesIO(data),read_only=True,data_only=True); return "\n".join(" | ".join(str(v) for v in row if v is not None) for sheet in book.worksheets for row in sheet.iter_rows(values_only=True))
    text=data.decode("utf-8",errors="replace")
    if mime=="text/html": parser=_HTML(); parser.feed(text); return "\n".join(parser.parts)
    return text


def chunks(text: str, size: int=1200, overlap: int=150) -> list[str]:
    clean=re.sub(r"\s+"," ",text).strip(); result=[]; start=0
    while start < len(clean): result.append(clean[start:start+size]); start += size-overlap
    return [item for item in result if item.strip()]


def embed(text: str, dimensions: int=64) -> list[float]:
    vector=[0.0]*dimensions
    for word in re.findall(r"\w+",text.lower()):
        digest=hashlib.sha256(word.encode()).digest(); vector[int.from_bytes(digest[:2],"big")%dimensions] += 1 if digest[2]%2 else -1
    norm=math.sqrt(sum(v*v for v in vector)) or 1.0; return [round(v/norm,6) for v in vector]


async def process_document(document_id: UUID, settings: Settings) -> None:
    engine=create_async_engine(settings.database_url); sessions=async_sessionmaker(engine,expire_on_commit=False)
    try:
        async with sessions() as db:
            doc=await db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.id==document_id))
            if not doc: return
            doc.status="processing"; doc.error_summary=None; await db.commit()
            try:
                client=storage(settings); response=await asyncio.to_thread(client.get_object,settings.storage_bucket,doc.storage_key)
                try: data=await asyncio.to_thread(response.read)
                finally: response.close(); response.release_conn()
                text=extract(data,doc.mime_type); parts=chunks(text)
                if not parts: raise ValueError("Nenhum texto útil foi extraído.")
                await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id==doc.id))
                for index,part in enumerate(parts): db.add(KnowledgeChunk(company_id=doc.company_id,knowledge_base_id=doc.knowledge_base_id,document_id=doc.id,chunk_index=index,content=part,token_count=max(1,len(part)//4),embedding_ref=f"sha256-64:{hashlib.sha256(part.encode()).hexdigest()[:24]}",embedding=embed(part),chunk_metadata={"document_name":doc.name}))
                doc.status="ready"; doc.processed_at=utc_now(); doc.document_metadata={**doc.document_metadata,"chunk_count":len(parts)}
            except Exception as exc:
                doc.status="error"; doc.error_summary=str(exc)[:1000]
            await db.commit()
    finally: await engine.dispose()


def process_document_sync(document_id: str) -> None: asyncio.run(process_document(UUID(document_id),get_settings()))


async def search_knowledge(db, *, company_id: UUID, base_id: UUID, query: str, limit: int=5) -> list[dict]:
    rows=(await db.scalars(select(KnowledgeChunk).join(KnowledgeDocument,KnowledgeDocument.id==KnowledgeChunk.document_id).where(KnowledgeChunk.company_id==company_id,KnowledgeChunk.knowledge_base_id==base_id,KnowledgeDocument.status=="ready").limit(2000))).all(); target=embed(query)
    scored=sorted(((sum(a*b for a,b in zip(target,row.embedding,strict=False)),row) for row in rows),key=lambda item:item[0],reverse=True)[:limit]
    return [{"chunk_id":str(row.id),"document_id":str(row.document_id),"document_name":row.chunk_metadata.get("document_name","Documento"),"chunk_index":row.chunk_index,"content":row.content,"score":round(score,4)} for score,row in scored if score>0]
