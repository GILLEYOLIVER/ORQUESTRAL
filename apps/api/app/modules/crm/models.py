from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
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


class CustomerDataSource(Base):
    __tablename__ = "customer_data_sources"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_customer_data_source_code"),
        CheckConstraint(
            "mode IN ('system_of_record', 'copied', 'federated', 'cached')",
            name="ck_customer_data_source_mode",
        ),
        CheckConstraint(
            "status IN ('active', 'paused', 'retired')",
            name="ck_customer_data_source_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    mode: Mapped[str] = mapped_column(
        String(24), default="system_of_record", server_default="system_of_record"
    )
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"
    __table_args__ = (
        CheckConstraint(
            "profile_type IN ('person', 'organization')",
            name="ck_customer_profile_type",
        ),
        CheckConstraint(
            "lifecycle_status IN ('lead', 'prospect', 'customer', 'inactive')",
            name="ck_customer_profile_lifecycle",
        ),
        CheckConstraint(
            "quality_score BETWEEN 0 AND 100",
            name="ck_customer_profile_quality",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    master_contact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("crm_contacts.id", ondelete="SET NULL"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(180), index=True)
    profile_type: Mapped[str] = mapped_column(String(20), default="person", server_default="person")
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), default="lead", server_default="lead", index=True
    )
    quality_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class CustomerProfileContact(Base):
    __tablename__ = "customer_profile_contacts"
    __table_args__ = (
        PrimaryKeyConstraint("profile_id", "contact_id"),
        CheckConstraint(
            "link_role IN ('master', 'matched', 'duplicate_candidate')",
            name="ck_customer_profile_contact_role",
        ),
        CheckConstraint(
            "match_confidence BETWEEN 0 AND 100",
            name="ck_customer_profile_contact_confidence",
        ),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer_profiles.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[UUID] = mapped_column(
        ForeignKey("crm_contacts.id", ondelete="CASCADE"), index=True
    )
    link_role: Mapped[str] = mapped_column(String(24))
    match_confidence: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


class CustomerIdentity(Base):
    __tablename__ = "customer_identities"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "identity_type",
            "value_hash",
            name="uq_customer_identity_fingerprint",
        ),
        CheckConstraint(
            "identity_type IN ('email', 'phone', 'external_id', 'document')",
            name="ck_customer_identity_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer_profiles.id", ondelete="CASCADE"), index=True
    )
    data_source_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer_data_sources.id", ondelete="RESTRICT"), index=True
    )
    identity_type: Mapped[str] = mapped_column(String(24), index=True)
    value_hash: Mapped[str] = mapped_column(String(64), index=True)
    display_hint: Mapped[str] = mapped_column(String(100))
    verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


class CustomerConsent(Base):
    __tablename__ = "customer_consents"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('marketing', 'service', 'analytics', 'ai_processing', 'data_sharing')",
            name="ck_customer_consent_purpose",
        ),
        CheckConstraint(
            "status IN ('granted', 'denied', 'revoked', 'expired')",
            name="ck_customer_consent_status",
        ),
        CheckConstraint(
            "channel IN ('all', 'email', 'phone', 'whatsapp', 'sms', 'web')",
            name="ck_customer_consent_channel",
        ),
        CheckConstraint(
            "expires_at IS NULL OR expires_at > captured_at",
            name="ck_customer_consent_expiry",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer_profiles.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(24), index=True)
    channel: Mapped[str] = mapped_column(String(16), default="all", server_default="all")
    status: Mapped[str] = mapped_column(String(16), index=True)
    lawful_basis: Mapped[str] = mapped_column(String(80))
    evidence_reference: Mapped[str | None] = mapped_column(String(240))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    recorded_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


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
