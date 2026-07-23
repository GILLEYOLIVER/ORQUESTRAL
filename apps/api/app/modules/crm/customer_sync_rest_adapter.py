from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import ValidationError

from app.core.secure_http import SecureHttpError, secure_https_get
from app.modules.crm.customer_ingestion_schemas import CustomerIngestionRecordInput


class RestPullAdapterError(ValueError):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class RestPullBatch:
    records: tuple[CustomerIngestionRecordInput, ...]
    cursor_after: str | None
    status_code: int
    response_bytes: int
    response_fingerprint: str


def _string_value(values: dict[str, Any], key: str, default: str = "") -> str:
    value = values.get(key, default)
    if value is None:
        return default
    if not isinstance(value, (str, int, float, bool)):
        raise RestPullAdapterError("CREDENTIAL_FORMAT_INVALID")
    return str(value).strip()


def _extract_path(payload: Any, path: str) -> Any:
    current = payload
    if not path:
        return current
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise RestPullAdapterError("RESPONSE_PATH_NOT_FOUND")
        current = current[segment]
    return current


def _request_url(credentials: dict[str, Any], cursor: str | None) -> str:
    base_url = _string_value(credentials, "base_url") or _string_value(credentials, "url")
    if not base_url:
        raise RestPullAdapterError("DESTINATION_URL_REQUIRED")
    parsed = urlsplit(base_url)
    query = list(parse_qsl(parsed.query, keep_blank_values=True))
    cursor_parameter = _string_value(credentials, "cursor_parameter", "cursor")
    if cursor and cursor_parameter:
        if not cursor_parameter.replace("_", "").isalnum() or len(cursor_parameter) > 80:
            raise RestPullAdapterError("CURSOR_PARAMETER_INVALID")
        query.append((cursor_parameter, cursor))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))


def _request_headers(credentials: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    raw_headers = credentials.get("headers", {})
    if raw_headers:
        if not isinstance(raw_headers, dict):
            raise RestPullAdapterError("CREDENTIAL_HEADERS_INVALID")
        for key, value in raw_headers.items():
            if not isinstance(value, (str, int, float, bool)):
                raise RestPullAdapterError("CREDENTIAL_HEADERS_INVALID")
            headers[str(key)] = str(value)
    api_key = _string_value(credentials, "api_key")
    if api_key:
        header_name = _string_value(credentials, "auth_header", "Authorization")
        headers[header_name] = api_key
    return headers


async def pull_customer_records(
    credentials: dict[str, Any],
    *,
    cursor: str | None,
    timeout_seconds: float,
    max_response_bytes: int,
) -> RestPullBatch:
    try:
        response = await secure_https_get(
            _request_url(credentials, cursor),
            headers=_request_headers(credentials),
            timeout_seconds=timeout_seconds,
            max_response_bytes=max_response_bytes,
        )
    except SecureHttpError as exc:
        raise RestPullAdapterError(
            exc.code,
            retryable=exc.retryable,
            status_code=exc.status_code,
        ) from exc
    if response.status_code in {408, 425, 429} or response.status_code >= 500:
        raise RestPullAdapterError(
            "REMOTE_TEMPORARY_FAILURE",
            retryable=True,
            status_code=response.status_code,
        )
    if response.status_code < 200 or response.status_code >= 300:
        raise RestPullAdapterError(
            "REMOTE_REQUEST_REJECTED",
            status_code=response.status_code,
        )
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"application/json", "application/problem+json"}:
        raise RestPullAdapterError("RESPONSE_CONTENT_TYPE_INVALID")
    try:
        decoded = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RestPullAdapterError("RESPONSE_JSON_INVALID") from exc
    records_value = (
        decoded
        if isinstance(decoded, list)
        else _extract_path(decoded, _string_value(credentials, "records_path", "records"))
    )
    if not isinstance(records_value, list) or len(records_value) > 100:
        raise RestPullAdapterError("RESPONSE_RECORDS_INVALID")
    try:
        records = tuple(CustomerIngestionRecordInput.model_validate(item) for item in records_value)
    except ValidationError as exc:
        raise RestPullAdapterError("RESPONSE_SCHEMA_INVALID") from exc
    cursor_after: str | None = None
    cursor_path = _string_value(credentials, "next_cursor_path", "next_cursor")
    if isinstance(decoded, dict) and cursor_path:
        try:
            cursor_value = _extract_path(decoded, cursor_path)
        except RestPullAdapterError:
            cursor_value = None
        if cursor_value is not None:
            cursor_after = str(cursor_value)
            if len(cursor_after) > 500:
                raise RestPullAdapterError("RESPONSE_CURSOR_INVALID")
    return RestPullBatch(
        records=records,
        cursor_after=cursor_after,
        status_code=response.status_code,
        response_bytes=len(response.body),
        response_fingerprint=hashlib.sha256(response.body).hexdigest(),
    )
