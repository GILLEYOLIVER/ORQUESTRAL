from __future__ import annotations

import hashlib
import secrets


def create_invitation_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hashlib.sha256(token.encode()).hexdigest()


def hash_invitation_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
