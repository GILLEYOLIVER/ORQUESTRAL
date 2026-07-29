from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field, HttpUrl, model_validator

from app.core.schemas import StrictSchema

SCIMScope = Literal["users.read", "users.write"]


def default_scim_scopes() -> list[SCIMScope]:
    return ["users.read", "users.write"]


class IdentityProviderCreate(StrictSchema):
    code: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9-]+$")
    name: str = Field(min_length=2, max_length=120)
    provider_type: Literal["oidc", "saml"]
    issuer: HttpUrl
    client_id: str | None = Field(default=None, max_length=255)
    client_secret: str | None = Field(default=None, min_length=16, max_length=500)
    authorization_endpoint: HttpUrl | None = None
    token_endpoint: HttpUrl | None = None
    jwks_uri: HttpUrl | None = None
    metadata_url: HttpUrl | None = None
    allowed_domains: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_provider_contract(self) -> IdentityProviderCreate:
        if self.provider_type == "oidc" and not all(
            (
                self.client_id,
                self.client_secret,
                self.authorization_endpoint,
                self.token_endpoint,
                self.jwks_uri,
            )
        ):
            raise ValueError("OIDC exige cliente, segredo e endpoints de autorização, token e JWKS.")
        if self.provider_type == "saml" and self.metadata_url is None:
            raise ValueError("SAML exige URL de metadados.")
        return self


class IdentityProviderResponse(StrictSchema):
    id: UUID
    code: str
    name: str
    provider_type: str
    issuer: str
    client_id: str | None
    client_secret_configured: bool
    authorization_endpoint: str | None
    token_endpoint: str | None
    jwks_uri: str | None
    metadata_url: str | None
    allowed_domains: list[str]
    status: str
    created_at: datetime
    updated_at: datetime


class SCIMTokenCreate(StrictSchema):
    name: str = Field(min_length=2, max_length=120)
    default_role_id: UUID
    scopes: list[SCIMScope] = Field(
        default_factory=default_scim_scopes,
        min_length=1,
        max_length=2,
    )
    expires_at: datetime


class SCIMTokenCreated(StrictSchema):
    id: UUID
    name: str
    token: str
    scopes: list[str]
    expires_at: datetime


class SCIMTokenResponse(StrictSchema):
    id: UUID
    name: str
    scopes: list[str]
    default_role_id: UUID
    status: str
    expires_at: datetime
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class SCIMUserCreate(StrictSchema):
    schemas: list[str] = Field(default_factory=lambda: ["urn:ietf:params:scim:schemas:core:2.0:User"])
    userName: EmailStr
    displayName: str = Field(min_length=2, max_length=160)
    externalId: str | None = Field(default=None, max_length=200)
    active: bool = True


class SCIMUserPatchOperation(StrictSchema):
    op: Literal["replace"]
    path: Literal["active"]
    value: bool


class SCIMUserPatch(StrictSchema):
    schemas: list[str] = Field(
        default_factory=lambda: ["urn:ietf:params:scim:api:messages:2.0:PatchOp"]
    )
    Operations: list[SCIMUserPatchOperation] = Field(min_length=1, max_length=10)


class SCIMUserResponse(StrictSchema):
    schemas: list[str]
    id: str
    userName: str
    displayName: str
    active: bool
    meta: dict[str, str]


class SCIMListResponse(StrictSchema):
    schemas: list[str]
    totalResults: int
    startIndex: int
    itemsPerPage: int
    Resources: list[SCIMUserResponse]
