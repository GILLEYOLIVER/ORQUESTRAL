from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,159}$")


def new_channel_public_key() -> str:
    return secrets.token_urlsafe(24)


def new_channel_secret() -> str:
    return secrets.token_urlsafe(48)


def secret_fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


def protected_reference(secret: str, value: str | None) -> str | None:
    if not value:
        return None
    return hmac.new(
        secret.encode("utf-8"),
        value.strip().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def sign_channel_request(secret: str, timestamp: str, body: bytes) -> str:
    message = timestamp.encode("ascii") + b"." + body
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_channel_request(
    secret: str,
    timestamp: str | None,
    body: bytes,
    signature: str | None,
    *,
    max_age_seconds: int,
    now: int | None = None,
) -> bool:
    if not timestamp or not signature:
        return False
    try:
        request_time = int(timestamp)
    except ValueError:
        return False
    current_time = int(time.time()) if now is None else now
    if abs(current_time - request_time) > max_age_seconds:
        return False
    expected = sign_channel_request(secret, timestamp, body)
    return hmac.compare_digest(expected, signature.strip())


def valid_idempotency_key(value: str | None) -> bool:
    return bool(value and _IDEMPOTENCY_KEY.fullmatch(value.strip()))
