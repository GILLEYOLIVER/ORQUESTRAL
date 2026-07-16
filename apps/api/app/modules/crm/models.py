from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    PrimaryKeyConstraint,
    String,
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
