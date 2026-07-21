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


class MetadataEntityDefinition(Base):
    __tablename__ = "metadata_entity_definitions"
    __table_args__ = (
        UniqueConstraint("company_id", "key", name="uq_metadata_entity_company_key"),
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_metadata_entity_status",
        ),
        Index("ix_metadata_entity_company_status", "company_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(120))
    plural_label: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="draft", server_default="draft")
    current_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    published_version: Mapped[int | None] = mapped_column(Integer)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
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


class MetadataEntityVersion(Base):
    __tablename__ = "metadata_entity_versions"
    __table_args__ = (
        UniqueConstraint("definition_id", "version", name="uq_metadata_entity_version_number"),
        CheckConstraint(
            "status IN ('draft', 'validated', 'published', 'retired')",
            name="ck_metadata_entity_version_status",
        ),
        CheckConstraint("version > 0", name="ck_metadata_entity_version_positive"),
        Index("ix_metadata_entity_version_company_status", "company_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("metadata_entity_definitions.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="draft", server_default="draft")
    schema_checksum: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )


class MetadataFieldDefinition(Base):
    __tablename__ = "metadata_field_definitions"
    __table_args__ = (
        UniqueConstraint("version_id", "key", name="uq_metadata_field_version_key"),
        CheckConstraint(
            "data_type IN ('text', 'long_text', 'integer', 'decimal', 'boolean', "
            "'date', 'datetime', 'email', 'phone', 'url', 'uuid', 'json')",
            name="ck_metadata_field_data_type",
        ),
        CheckConstraint("position >= 0", name="ck_metadata_field_position_nonnegative"),
        Index("ix_metadata_field_company_version", "company_id", "version_id"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("metadata_entity_versions.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(120))
    data_type: Mapped[str] = mapped_column(String(24))
    required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    unique_values: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    searchable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    default_value: Mapped[Any | None] = mapped_column(JSONB)
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
