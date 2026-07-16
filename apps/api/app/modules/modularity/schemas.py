from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.core.schemas import StrictSchema


class ModuleResponse(StrictSchema):
    id: UUID
    code: str
    name: str
    description: str
    version: str
    category: str
    is_core: bool
    catalog_status: str
    installed: bool
    company_status: Literal["active", "inactive"]
    configuration: dict[str, Any]
    activated_at: datetime | None
    deactivated_at: datetime | None


class CompanyModuleUpdate(StrictSchema):
    status: Literal["active", "inactive"]
    configuration: dict[str, Any] | None = Field(default=None)
