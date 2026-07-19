from __future__ import annotations

import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, cast
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings

_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65_536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


class InvalidAccessTokenError(ValueError):
    pass


class WeakPasswordError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: UUID
    session_id: UUID
    company_id: UUID | None
    expires_at: datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def validate_password_strength(password: str) -> None:
    if len(password) < 12:
        raise WeakPasswordError("A senha deve possuir pelo menos 12 caracteres.")
    rules = (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]")
    if not all(re.search(rule, password) for rule in rules):
        raise WeakPasswordError("Use letras maiúsculas e minúsculas, número e caractere especial.")


def hash_password(password: str) -> str:
    validate_password_strength(password)
    return _password_hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    if not password_hash:
        return False
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _password_hasher.check_needs_rehash(password_hash)


def create_access_token(
    settings: Settings,
    *,
    user_id: UUID,
    session_id: UUID,
    company_id: UUID | None,
) -> tuple[str, datetime]:
    issued_at = utc_now()
    expires_at = issued_at + timedelta(minutes=settings.access_token_minutes)
    payload: dict[str, Any] = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": str(user_id),
        "sid": str(session_id),
        "type": "access",
        "jti": str(uuid4()),
        "iat": issued_at,
        "exp": expires_at,
    }
    if company_id is not None:
        payload["company_id"] = str(company_id)
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256"), expires_at


def decode_access_token(settings: Settings, token: str) -> AccessTokenClaims:
    payload: dict[str, Any] | None = None
    for secret in settings.jwt_verification_secrets:
        try:
            payload = cast(
                dict[str, Any],
                jwt.decode(
                    token,
                    secret,
                    algorithms=["HS256"],
                    audience=settings.jwt_audience,
                    issuer=settings.jwt_issuer,
                    options={"require": ["exp", "iat", "jti", "sub", "sid", "type"]},
                ),
            )
            break
        except jwt.InvalidTokenError:
            continue
    if payload is None:
        raise InvalidAccessTokenError("Token de acesso inválido")
    try:
        if payload["type"] != "access":
            raise InvalidAccessTokenError("Tipo de token inválido")
        company_value = payload.get("company_id")
        return AccessTokenClaims(
            user_id=UUID(str(payload["sub"])),
            session_id=UUID(str(payload["sid"])),
            company_id=UUID(str(company_value)) if company_value else None,
            expires_at=datetime.fromtimestamp(float(payload["exp"]), tz=UTC),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidAccessTokenError("Token de acesso inválido") from exc


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_opaque_token(settings: Settings, token: str) -> str:
    return hmac.new(settings.encryption_key.encode(), token.encode(), digestmod=sha256).hexdigest()
