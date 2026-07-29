from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EnterpriseIdentityProvider(Base):
    __tablename__ = "enterprise_identity_providers"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "code", name="uq_enterprise_identity_providers_company_code"
        ),
        CheckConstraint(
            "provider_type IN ('oidc', 'saml')",
            name="ck_enterprise_identity_providers_type",
        ),
        CheckConstraint(
            "status IN ('configured', 'active', 'disabled', 'error')",
            name="ck_enterprise_identity_providers_status",
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
    provider_type: Mapped[str] = mapped_column(String(20))
    issuer: Mapped[str] = mapped_column(String(500))
    client_id: Mapped[str | None] = mapped_column(String(255))
    encrypted_client_secret: Mapped[bytes | None] = mapped_column(LargeBinary)
    authorization_endpoint: Mapped[str | None] = mapped_column(String(500))
    token_endpoint: Mapped[str | None] = mapped_column(String(500))
    jwks_uri: Mapped[str | None] = mapped_column(String(500))
    metadata_url: Mapped[str | None] = mapped_column(String(500))
    allowed_domains: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    status: Mapped[str] = mapped_column(
        String(20), default="configured", server_default="configured"
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )


class SCIMProvisioningToken(Base):
    __tablename__ = "scim_provisioning_tokens"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'revoked', 'expired')",
            name="ck_scim_provisioning_tokens_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list[str]] = mapped_column(JSONB)
    default_role_id: Mapped[UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
