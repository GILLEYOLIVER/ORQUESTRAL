from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, LargeBinary, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Plugin(Base):
    __tablename__ = "plugins"
    __table_args__ = (
        CheckConstraint("status IN ('installed', 'planned', 'disabled')", name="ck_plugins_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    code: Mapped[str] = mapped_column(CITEXT(), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(500))
    authentication_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), index=True)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now())


class CompanyPlugin(Base):
    __tablename__ = "company_plugins"
    __table_args__ = (
        UniqueConstraint("company_id", "plugin_id", name="uq_company_plugins_company_plugin"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_company_plugins_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    plugin_id: Mapped[UUID] = mapped_column(ForeignKey("plugins.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="inactive", server_default="inactive")
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IntegrationCredential(Base):
    __tablename__ = "integration_credentials"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'expired', 'revoked')", name="ck_integration_credentials_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    plugin_id: Mapped[UUID] = mapped_column(ForeignKey("plugins.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    encrypted_credentials: Mapped[bytes] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now())
