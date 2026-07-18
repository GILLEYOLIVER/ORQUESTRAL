from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class CredentialVaultError(ValueError):
    pass


class CredentialVault:
    def __init__(self, secret: str) -> None:
        secrets = [value.strip() for value in secret.split(",") if value.strip()]
        if not secrets:
            raise CredentialVaultError("Nenhuma chave de criptografia foi configurada.")
        self._fernets = [self._build_fernet(value) for value in secrets]
        self._primary = self._fernets[0]
        self._multi = MultiFernet(self._fernets)

    @staticmethod
    def _build_fernet(secret: str) -> Fernet:
        digest = hashlib.sha256(secret.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, values: dict[str, Any]) -> bytes:
        payload = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return self._primary.encrypt(payload)

    def decrypt(self, encrypted: bytes) -> dict[str, Any]:
        try:
            decoded = self._multi.decrypt(encrypted)
            value = json.loads(decoded.decode("utf-8"))
        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CredentialVaultError("Não foi possível descriptografar as credenciais.") from exc
        if not isinstance(value, dict):
            raise CredentialVaultError("O conteúdo criptografado possui formato inválido.")
        return value

    def rotate(self, encrypted: bytes) -> bytes:
        try:
            return self._multi.rotate(encrypted)
        except InvalidToken as exc:
            raise CredentialVaultError(
                "A credencial não pode ser rotacionada com as chaves configuradas."
            ) from exc


def mask_credentials(values: dict[str, Any]) -> dict[str, str]:
    masked: dict[str, str] = {}
    for key, value in values.items():
        text = str(value)
        masked[key] = "••••••••" if text else ""
    return masked


def mask_credential_fields(fields: list[str]) -> dict[str, str]:
    return {field: "••••••••" for field in fields}
