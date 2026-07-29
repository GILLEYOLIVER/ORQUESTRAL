from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeveloperSandbox(Base):
    __tablename__ = "developer_sandboxes"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_developer_sandboxes_company_code"),
        CheckConstraint(
            "environment IN ('development', 'testing', 'staging')",
            name="ck_developer_sandboxes_environment",
        ),
        CheckConstraint(
            "data_policy IN ('empty', 'synthetic', 'masked')",
            name="ck_developer_sandboxes_data_policy",
        ),
        CheckConstraint(
            "status IN ('active', 'archived')", name="ck_developer_sandboxes_status"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    environment: Mapped[str] = mapped_column(String(20))
    data_policy: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ArtifactPromotion(Base):
    __tablename__ = "artifact_promotions"
    __table_args__ = (
        CheckConstraint(
            "artifact_type IN ('metadata', 'automation', 'agent', 'plugin')",
            name="ck_artifact_promotions_type",
        ),
        CheckConstraint(
            "source_environment IN ('local', 'development', 'testing', 'staging')",
            name="ck_artifact_promotions_source",
        ),
        CheckConstraint(
            "target_environment IN ('development', 'testing', 'staging', 'production')",
            name="ck_artifact_promotions_target",
        ),
        CheckConstraint(
            "status IN ('requested', 'approved', 'rejected', 'applied', 'failed')",
            name="ck_artifact_promotions_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(20))
    artifact_ref: Mapped[str] = mapped_column(String(200))
    source_environment: Mapped[str] = mapped_column(String(20))
    target_environment: Mapped[str] = mapped_column(String(20))
    checksum: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="requested", server_default="requested")
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
