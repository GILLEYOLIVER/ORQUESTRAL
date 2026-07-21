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


class MetadataLayoutDefinition(Base):
    __tablename__ = "metadata_layout_definitions"
    __table_args__ = (
        UniqueConstraint("company_id", "version_id", "key", name="uq_metadata_layout_key"),
        Index("ix_metadata_layout_company_version", "company_id", "version_id"),
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
    sections: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


class MetadataViewDefinition(Base):
    __tablename__ = "metadata_view_definitions"
    __table_args__ = (
        UniqueConstraint("company_id", "version_id", "key", name="uq_metadata_view_key"),
        Index("ix_metadata_view_company_version", "company_id", "version_id"),
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
    columns: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    filters: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    sorting: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


class MetadataValidationRule(Base):
    __tablename__ = "metadata_validation_rules"
    __table_args__ = (
        UniqueConstraint("company_id", "version_id", "key", name="uq_metadata_validation_rule_key"),
        CheckConstraint(
            "operator IN ('equals', 'not_equals', 'greater_than', 'less_than', "
            "'contains', 'is_empty', 'is_not_empty')",
            name="ck_metadata_validation_rule_operator",
        ),
        Index("ix_metadata_validation_rule_company_version", "company_id", "version_id"),
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
    field_key: Mapped[str] = mapped_column(String(80))
    operator: Mapped[str] = mapped_column(String(24))
    comparison_value: Mapped[Any | None] = mapped_column(JSONB)
    message: Mapped[str] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


class MetadataRelationshipDefinition(Base):
    __tablename__ = "metadata_relationship_definitions"
    __table_args__ = (
        UniqueConstraint("company_id", "version_id", "key", name="uq_metadata_relationship_key"),
        CheckConstraint(
            "relationship_type IN ('many_to_one', 'one_to_one')",
            name="ck_metadata_relationship_type",
        ),
        CheckConstraint("on_delete = 'restrict'", name="ck_metadata_relationship_on_delete"),
        Index("ix_metadata_relationship_company_version", "company_id", "version_id"),
        Index("ix_metadata_relationship_target", "company_id", "target_definition_id"),
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
    source_field_key: Mapped[str] = mapped_column(String(80))
    target_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("metadata_entity_definitions.id", ondelete="RESTRICT"), index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(24))
    on_delete: Mapped[str] = mapped_column(
        String(16), default="restrict", server_default="restrict"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


class MetadataFormulaDefinition(Base):
    __tablename__ = "metadata_formula_definitions"
    __table_args__ = (
        UniqueConstraint("company_id", "version_id", "key", name="uq_metadata_formula_key"),
        UniqueConstraint(
            "company_id",
            "version_id",
            "target_field_key",
            name="uq_metadata_formula_target",
        ),
        Index("ix_metadata_formula_company_version", "company_id", "version_id"),
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
    target_field_key: Mapped[str] = mapped_column(String(80))
    expression: Mapped[dict[str, Any]] = mapped_column(JSONB)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


class MetadataRecordTypeDefinition(Base):
    __tablename__ = "metadata_record_type_definitions"
    __table_args__ = (
        UniqueConstraint("company_id", "version_id", "key", name="uq_metadata_record_type_key"),
        Index("ix_metadata_record_type_company_version", "company_id", "version_id"),
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
    description: Mapped[str | None] = mapped_column(Text)
    layout_key: Mapped[str] = mapped_column(String(80))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


class MetadataRecord(Base):
    __tablename__ = "metadata_records"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "definition_id",
            "idempotency_key",
            name="uq_metadata_record_idempotency",
        ),
        CheckConstraint("record_version > 0", name="ck_metadata_record_version_positive"),
        Index(
            "ix_metadata_record_company_definition_active",
            "company_id",
            "definition_id",
            "deleted_at",
        ),
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
    schema_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("metadata_entity_versions.id", ondelete="RESTRICT"), index=True
    )
    schema_version: Mapped[int] = mapped_column(Integer)
    record_type_key: Mapped[str | None] = mapped_column(String(80))
    values: Mapped[dict[str, Any]] = mapped_column(JSONB)
    record_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    idempotency_key: Mapped[UUID | None]
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
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
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class MetadataRecordRevision(Base):
    __tablename__ = "metadata_record_revisions"
    __table_args__ = (
        UniqueConstraint("record_id", "revision", name="uq_metadata_record_revision"),
        CheckConstraint("revision > 0", name="ck_metadata_record_revision_positive"),
        CheckConstraint(
            "change_type IN ('created', 'updated')",
            name="ck_metadata_record_revision_change_type",
        ),
        Index(
            "ix_metadata_record_revision_company_record",
            "company_id",
            "record_id",
        ),
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
    record_id: Mapped[UUID] = mapped_column(
        ForeignKey("metadata_records.id", ondelete="CASCADE"), index=True
    )
    schema_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("metadata_entity_versions.id", ondelete="RESTRICT")
    )
    schema_version: Mapped[int] = mapped_column(Integer)
    record_type_key: Mapped[str | None] = mapped_column(String(80))
    revision: Mapped[int] = mapped_column(Integer)
    change_type: Mapped[str] = mapped_column(String(16))
    values: Mapped[dict[str, Any]] = mapped_column(JSONB)
    changed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


class MetadataPackageCatalog(Base):
    __tablename__ = "metadata_package_catalogs"
    __table_args__ = (
        UniqueConstraint("company_id", "key", name="uq_metadata_package_catalog_key"),
        Index("ix_metadata_package_catalog_company", "company_id", "key"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
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


class MetadataPackageVersion(Base):
    __tablename__ = "metadata_package_versions"
    __table_args__ = (
        UniqueConstraint(
            "package_catalog_id", "version", name="uq_metadata_package_version_number"
        ),
        CheckConstraint(
            "status IN ('draft', 'validated', 'published', 'retired')",
            name="ck_metadata_package_version_status",
        ),
        CheckConstraint(
            "source_environment IN ('local', 'testing', 'development', 'staging', 'production')",
            name="ck_metadata_package_source_environment",
        ),
        Index("ix_metadata_package_version_company_status", "company_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    package_catalog_id: Mapped[UUID] = mapped_column(
        ForeignKey("metadata_package_catalogs.id", ondelete="CASCADE"), index=True
    )
    entity_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("metadata_entity_definitions.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="draft", server_default="draft")
    source_environment: Mapped[str] = mapped_column(String(16))
    dependencies: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    artifact: Mapped[dict[str, Any]] = mapped_column(JSONB)
    checksum: Mapped[str] = mapped_column(String(64))
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


class MetadataPackageInstallation(Base):
    __tablename__ = "metadata_package_installations"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "package_key",
            "package_version",
            "target_environment",
            name="uq_metadata_package_installation_release",
        ),
        CheckConstraint(
            "status IN ('installed', 'removed')",
            name="ck_metadata_package_installation_status",
        ),
        CheckConstraint(
            "target_environment IN ('local', 'testing', 'development', 'staging', 'production')",
            name="ck_metadata_package_target_environment",
        ),
        Index(
            "ix_metadata_package_installation_company_status",
            "company_id",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    package_key: Mapped[str] = mapped_column(String(80))
    package_version: Mapped[str] = mapped_column(String(32))
    source_checksum: Mapped[str] = mapped_column(String(64))
    target_environment: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="installed", server_default="installed")
    installed_definition_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("metadata_entity_definitions.id", ondelete="SET NULL"), index=True
    )
    installed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
