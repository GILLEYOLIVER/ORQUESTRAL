from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

REDACTED = "[REDACTED]"
_SENSITIVE_EXACT = frozenset(
    {
        "authorization",
        "cookie",
        "set_cookie",
        "password",
        "password_hash",
        "refresh_token",
        "access_token",
        "api_key",
        "client_secret",
        "credential",
        "credentials",
    }
)
_SENSITIVE_SUFFIXES = (
    "_password",
    "_password_hash",
    "_secret",
    "_token",
    "_api_key",
    "_credential",
    "_credentials",
)


def is_sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    return normalized in _SENSITIVE_EXACT or normalized.endswith(_SENSITIVE_SUFFIXES)


def redact_sensitive_data(value: Any, *, depth: int = 0) -> Any:
    """Retorna uma estrutura segura para auditoria e logs estruturados."""
    if depth >= 8:
        return "[MAX_DEPTH]"
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED
            if is_sensitive_key(key)
            else redact_sensitive_data(item, depth=depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_sensitive_data(item, depth=depth + 1) for item in value]
    if isinstance(value, (bytes, bytearray)):
        return f"[BINARY:{len(value)} bytes]"
    if isinstance(value, str) and len(value) > 2_048:
        return f"{value[:2_048]}...[TRUNCATED]"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def redact_structlog_event(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> Mapping[str, Any]:
    return {
        key: REDACTED if is_sensitive_key(key) else redact_sensitive_data(value)
        for key, value in event_dict.items()
    }
