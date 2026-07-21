from __future__ import annotations

import base64
import hmac
import os
from hashlib import sha256

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import Settings

_VERSION = "v1"
_DOMAIN = b"orkestral-field-encryption-v1"


class FieldDecryptionError(ValueError):
    pass


def _derive_key(secret: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), _DOMAIN, sha256).digest()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def encrypt_text(settings: Settings, plaintext: str, *, associated_data: str) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_derive_key(settings.encryption_key)).encrypt(
        nonce,
        plaintext.encode("utf-8"),
        associated_data.encode("utf-8"),
    )
    return f"{_VERSION}.{_encode(nonce)}.{_encode(ciphertext)}"


def decrypt_text(settings: Settings, token: str, *, associated_data: str) -> str:
    try:
        version, nonce_value, ciphertext_value = token.split(".", maxsplit=2)
        if version != _VERSION:
            raise FieldDecryptionError("Versão criptográfica não suportada")
        nonce = _decode(nonce_value)
        ciphertext = _decode(ciphertext_value)
    except (ValueError, TypeError) as exc:
        raise FieldDecryptionError("Conteúdo criptografado inválido") from exc
    for secret in (settings.encryption_key, *settings.encryption_previous_keys):
        try:
            plaintext = AESGCM(_derive_key(secret)).decrypt(
                nonce,
                ciphertext,
                associated_data.encode("utf-8"),
            )
            return plaintext.decode("utf-8")
        except (InvalidTag, UnicodeDecodeError):
            continue
    raise FieldDecryptionError("Não foi possível autenticar o conteúdo criptografado")
