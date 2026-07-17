from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class CredentialVaultError(ValueError):
    pass


class CredentialVault:
    def __init__(self, secret: str) -> None:
        digest = hashlib.sha256(secret.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, values: dict[str, Any]) -> bytes:
        payload = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return self._fernet.encrypt(payload)

    def decrypt(self, encrypted: bytes) -> dict[str, Any]:
        try:
            decoded = self._fernet.decrypt(encrypted)
            value = json.loads(decoded.decode("utf-8"))
        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CredentialVaultError("Não foi possível descriptografar as credenciais.") from exc
        if not isinstance(value, dict):
            raise CredentialVaultError("O conteúdo criptografado possui formato inválido.")
        return value


def mask_credentials(values: dict[str, Any]) -> dict[str, str]:
    masked: dict[str, str] = {}
    for key, value in values.items():
        text = str(value)
        masked[key] = "••••••••" if text else ""
    return masked
