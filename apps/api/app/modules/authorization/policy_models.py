from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.security import utc_now


class PolicyDecisionRecord(Base):
    __tablename__ = "policy_decisions"
    __table_args__ = (
        Index("ix_policy_decisions_company_created", "company_id", "created_at"),
        Index("ix_policy_decisions_company_outcome", "company_id", "outcome"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    correlation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    required_permission: Mapped[str | None] = mapped_column(String(160), nullable=True)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    requested_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    allowed_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    denied_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    risk_level: Mapped[str] = mapped_column(String(24), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
