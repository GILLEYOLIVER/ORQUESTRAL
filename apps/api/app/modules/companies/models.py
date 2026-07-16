from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'suspended', 'trial', 'cancelled')",
            name="ck_companies_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    legal_name: Mapped[str] = mapped_column(String(200))
    trade_name: Mapped[str] = mapped_column(String(200))
    document_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    slug: Mapped[str] = mapped_column(CITEXT(), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="trial", server_default="trial")
    timezone: Mapped[str] = mapped_column(
        String(64), default="America/Sao_Paulo", server_default="America/Sao_Paulo"
    )
    language: Mapped[str] = mapped_column(String(16), default="pt-BR", server_default="pt-BR")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
