from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentMemoryPolicy(Base):
    __tablename__ = "agent_memory_policies"
    __table_args__ = (
        UniqueConstraint("agent_id", name="uq_agent_memory_policies_agent"),
        CheckConstraint(
            "default_retention_days BETWEEN 1 AND 3650",
            name="ck_agent_memory_policy_default_retention",
        ),
        CheckConstraint(
            "max_retention_days BETWEEN default_retention_days AND 3650",
            name="ck_agent_memory_policy_max_retention",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    default_retention_days: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    max_retention_days: Mapped[int] = mapped_column(Integer, default=365, server_default="365")
    allowed_scopes: Mapped[list[str]] = mapped_column(
        JSONB,
        default=lambda: ["conversation", "task", "operational"],
        server_default=text('\'["conversation","task","operational"]\'::jsonb'),
    )
    allowed_classifications: Mapped[list[str]] = mapped_column(
        JSONB,
        default=lambda: ["public", "internal"],
        server_default=text('\'["public","internal"]\'::jsonb'),
    )
    require_consent_for_user_scope: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    updated_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class AgentMemoryEntry(Base):
    __tablename__ = "agent_memory_entries"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "agent_id", "content_fingerprint", name="uq_agent_memory_content"
        ),
        CheckConstraint(
            "scope IN ('conversation', 'task', 'user', 'company', 'operational')",
            name="ck_agent_memory_scope",
        ),
        CheckConstraint(
            "classification IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_agent_memory_classification",
        ),
        CheckConstraint(
            "source_type IN ('manual', 'conversation', 'task', 'tool')",
            name="ck_agent_memory_source_type",
        ),
        CheckConstraint("expires_at > created_at", name="ck_agent_memory_expiration"),
        CheckConstraint(
            "scope <> 'user' OR consent_reference IS NOT NULL",
            name="ck_agent_memory_user_consent",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    scope: Mapped[str] = mapped_column(String(24), index=True)
    classification: Mapped[str] = mapped_column(String(24), index=True)
    encrypted_content: Mapped[bytes] = mapped_column(LargeBinary)
    content_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    source_type: Mapped[str] = mapped_column(String(24), default="manual", server_default="manual")
    source_id: Mapped[str | None] = mapped_column(String(160))
    consent_reference: Mapped[str | None] = mapped_column(String(160))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
