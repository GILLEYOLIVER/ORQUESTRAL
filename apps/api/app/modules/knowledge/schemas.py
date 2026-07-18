from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import Field
from app.core.schemas import StrictSchema

class BaseCreate(StrictSchema): name:str=Field(min_length=2,max_length=160); description:str|None=Field(default=None,max_length=500)
class BaseResponse(StrictSchema): id:UUID; name:str; description:str|None; status:str; created_at:datetime; updated_at:datetime
class DocumentResponse(StrictSchema): id:UUID; knowledge_base_id:UUID; name:str; source_type:str; source_url:str|None; mime_type:str; size_bytes:int; checksum_sha256:str; status:str; document_metadata:dict[str,Any]; error_summary:str|None; processed_at:datetime|None; created_at:datetime
class URLImport(StrictSchema): url:str=Field(min_length=10,max_length=1000); name:str|None=Field(default=None,max_length=255)
class SearchResult(StrictSchema): chunk_id:UUID; document_id:UUID; document_name:str; chunk_index:int; content:str; score:float
