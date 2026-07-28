from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SupportResponseTemplate(Base):
    __tablename__ = "support_response_templates"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('macro','quick_response')",
            name="ck_support_response_templates_kind",
        ),
        UniqueConstraint(
            "company_id", "shortcut", name="uq_support_response_templates_company_shortcut"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), index=True)
    shortcut: Mapped[str] = mapped_column(String(80), index=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    content: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), index=True
    )
    usage_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )


class SupportResponseCitation(Base):
    __tablename__ = "support_response_citations"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "interaction_id",
            "knowledge_chunk_id",
            name="uq_support_response_citations_interaction_chunk",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("support_tickets.id", ondelete="CASCADE"), index=True
    )
    interaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("support_interactions.id", ondelete="CASCADE"), index=True
    )
    knowledge_base_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="RESTRICT"), index=True
    )
    knowledge_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="RESTRICT"), index=True
    )
    knowledge_chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_chunks.id", ondelete="RESTRICT"), index=True
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    excerpt_sha256: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


class SupportSatisfactionSurvey(Base):
    __tablename__ = "support_satisfaction_surveys"
    __table_args__ = (
        CheckConstraint("overall_score BETWEEN 1 AND 5", name="ck_support_survey_overall"),
        CheckConstraint(
            "resolution_score BETWEEN 1 AND 5", name="ck_support_survey_resolution"
        ),
        CheckConstraint("effort_score BETWEEN 1 AND 5", name="ck_support_survey_effort"),
        UniqueConstraint(
            "company_id", "ticket_id", name="uq_support_satisfaction_surveys_company_ticket"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("support_tickets.id", ondelete="CASCADE"), index=True
    )
    recorded_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    overall_score: Mapped[int] = mapped_column(Integer, index=True)
    resolution_score: Mapped[int] = mapped_column(Integer, index=True)
    effort_score: Mapped[int] = mapped_column(Integer, index=True)
    comment_sha256: Mapped[str | None] = mapped_column(String(64))
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )

