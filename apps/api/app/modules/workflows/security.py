from __future__ import annotations

import hmac
import secrets
from hashlib import sha256


def new_webhook_key() -> str:
    return secrets.token_urlsafe(24)


def new_webhook_secret() -> str:
    return secrets.token_urlsafe(48)


def new_internal_webhook_path() -> str:
    return f"orkestral-internal-{secrets.token_urlsafe(36)}"


def sign_webhook_body(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, sha256).hexdigest()
    return f"sha256={digest}"


def verify_webhook_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    return hmac.compare_digest(sign_webhook_body(secret, body), signature.strip())
