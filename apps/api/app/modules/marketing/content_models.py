from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketingChannelConnector(Base):
    __tablename__ = "marketing_channel_connectors"
    __table_args__ = (
        CheckConstraint("channel IN ('email','whatsapp','sms','web')", name="ck_marketing_channel_connectors_channel"),
        CheckConstraint("status IN ('draft','active','disabled','error')", name="ck_marketing_channel_connectors_status"),
        UniqueConstraint("company_id", "channel", "provider", name="uq_marketing_channel_connectors_provider"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    credential_id: Mapped[UUID | None] = mapped_column(ForeignKey("integration_credentials.id", ondelete="SET NULL"), index=True)
    channel: Mapped[str] = mapped_column(String(16), index=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    sender_reference: Mapped[str | None] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(16), default="draft", server_default="draft", index=True)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now())


class MarketingContent(Base):
    __tablename__ = "marketing_contents"
    __table_args__ = (
        CheckConstraint("kind IN ('email','whatsapp','sms','landing_page')", name="ck_marketing_contents_kind"),
        CheckConstraint("status IN ('draft','in_review','approved','archived')", name="ck_marketing_contents_status"),
        Index("ix_marketing_contents_company_status", "company_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    status: Mapped[str] = mapped_column(String(16), default="draft", server_default="draft", index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now())


class MarketingContentVersion(Base):
    __tablename__ = "marketing_content_versions"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_marketing_content_versions_version"),
        CheckConstraint("review_status IN ('draft','pending','approved','rejected')", name="ck_marketing_content_versions_review"),
        UniqueConstraint("content_id", "version", name="uq_marketing_content_versions_number"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    content_id: Mapped[UUID] = mapped_column(ForeignKey("marketing_contents.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    subject: Mapped[str | None] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    review_status: Mapped[str] = mapped_column(String(16), default="draft", server_default="draft", index=True)
    review_notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now())


class MarketingLandingPage(Base):
    __tablename__ = "marketing_landing_pages"
    __table_args__ = (
        CheckConstraint("status IN ('draft','published','paused','archived')", name="ck_marketing_landing_pages_status"),
        UniqueConstraint("company_id", "slug", name="uq_marketing_landing_pages_slug"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    public_id: Mapped[UUID] = mapped_column(default=uuid4, server_default=text("gen_random_uuid()"), unique=True, index=True)
    content_id: Mapped[UUID] = mapped_column(ForeignKey("marketing_contents.id", ondelete="RESTRICT"), index=True)
    slug: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(16), default="draft", server_default="draft", index=True)
    form_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now())


class MarketingPublicPageRegistry(Base):
    __tablename__ = "marketing_public_page_registry"

    public_id: Mapped[UUID] = mapped_column(primary_key=True)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    page_id: Mapped[UUID] = mapped_column(ForeignKey("marketing_landing_pages.id", ondelete="CASCADE"), unique=True)


class MarketingFormSubmission(Base):
    __tablename__ = "marketing_form_submissions"
    __table_args__ = (
        CheckConstraint("status IN ('accepted','rejected','spam')", name="ck_marketing_form_submissions_status"),
        Index("ix_marketing_form_submissions_company_page", "company_id", "page_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    page_id: Mapped[UUID] = mapped_column(ForeignKey("marketing_landing_pages.id", ondelete="CASCADE"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    consent_granted: Mapped[bool] = mapped_column(Boolean)
    source_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="accepted", server_default="accepted", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True)
