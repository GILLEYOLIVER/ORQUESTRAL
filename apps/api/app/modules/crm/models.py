from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CRMContact(Base):
    __tablename__ = "crm_contacts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('lead', 'prospect', 'customer', 'inactive')",
            name="ck_crm_contacts_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), index=True)
    email: Mapped[str | None] = mapped_column(CITEXT(), index=True)
    phone: Mapped[str | None] = mapped_column(String(64))
    company_name: Mapped[str | None] = mapped_column(String(180), index=True)
    job_title: Mapped[str | None] = mapped_column(String(120))
    source: Mapped[str | None] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="lead", server_default="lead", index=True
    )
    assigned_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class CRMTag(Base):
    __tablename__ = "crm_tags"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_crm_tags_company_name"),)

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(CITEXT(), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


class CRMContactTag(Base):
    __tablename__ = "crm_contact_tags"
    __table_args__ = (PrimaryKeyConstraint("contact_id", "tag_id"),)

    contact_id: Mapped[UUID] = mapped_column(
        ForeignKey("crm_contacts.id", ondelete="CASCADE"), index=True
    )
    tag_id: Mapped[UUID] = mapped_column(ForeignKey("crm_tags.id", ondelete="CASCADE"), index=True)


class CRMPipeline(Base):
    __tablename__ = "crm_pipelines"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_crm_pipeline_company_name"),)

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    is_default: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class CRMPipelineStage(Base):
    __tablename__ = "crm_pipeline_stages"
    __table_args__ = (
        UniqueConstraint("pipeline_id", "name", name="uq_crm_pipeline_stage_name"),
        CheckConstraint("position >= 0", name="ck_crm_pipeline_stage_position"),
        CheckConstraint(
            "probability >= 0 AND probability <= 100",
            name="ck_crm_pipeline_stage_probability",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    pipeline_id: Mapped[UUID] = mapped_column(
        ForeignKey("crm_pipelines.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    position: Mapped[int] = mapped_column(default=0, server_default="0")
    probability: Mapped[int] = mapped_column(default=0, server_default="0")
    color: Mapped[str] = mapped_column(String(20), default="#2f6f64", server_default="#2f6f64")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class CRMOpportunity(Base):
    __tablename__ = "crm_opportunities"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_crm_opportunity_amount"),
        CheckConstraint(
            "probability IS NULL OR (probability >= 0 AND probability <= 100)",
            name="ck_crm_opportunity_probability",
        ),
        CheckConstraint(
            "status IN ('open', 'won', 'lost')",
            name="ck_crm_opportunity_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    pipeline_id: Mapped[UUID] = mapped_column(
        ForeignKey("crm_pipelines.id", ondelete="RESTRICT"), index=True
    )
    stage_id: Mapped[UUID] = mapped_column(
        ForeignKey("crm_pipeline_stages.id", ondelete="RESTRICT"), index=True
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("crm_contacts.id", ondelete="SET NULL"), index=True
    )
    assigned_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), default=Decimal("0"), server_default="0"
    )
    probability: Mapped[int | None]
    expected_close_date: Mapped[date | None]
    source: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), default="open", server_default="open")
    lost_reason: Mapped[str | None] = mapped_column(String(240))
    notes: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class CRMOpportunityActivity(Base):
    __tablename__ = "crm_opportunity_activities"
    __table_args__ = (
        CheckConstraint(
            "activity_type IN ('note', 'call', 'email', 'meeting', 'stage_change', 'status_change')",
            name="ck_crm_opportunity_activity_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[UUID] = mapped_column(
        ForeignKey("crm_opportunities.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("crm_contacts.id", ondelete="SET NULL"), index=True
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    activity_type: Mapped[str] = mapped_column(String(24), default="note", server_default="note")
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
