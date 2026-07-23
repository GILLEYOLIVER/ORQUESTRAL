from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit

_HEADER_NAME = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]{1,80}$")
_BLOCKED_REQUEST_HEADERS = {
    "connection",
    "content-length",
    "host",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
_BLOCKED_HOST_SUFFIXES = (
    ".home.arpa",
    ".internal",
    ".lan",
    ".local",
    ".localhost",
    ".onion",
)
_MAX_HEADER_BYTES = 65_536


class SecureHttpError(ValueError):
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
class SecureHttpsDestination:
    url: str
    host: str
    port: int
    request_target: str


@dataclass(frozen=True, slots=True)
class SecureHttpResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes


def is_public_network_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def validate_https_destination(url: str) -> SecureHttpsDestination:
    if len(url) > 2_048:
        raise SecureHttpError("URL_TOO_LONG")
    parsed: SplitResult = urlsplit(url)
    host = (parsed.hostname or "").strip().rstrip(".").lower()
    if parsed.scheme.lower() != "https":
        raise SecureHttpError("HTTPS_REQUIRED")
    if not host:
        raise SecureHttpError("DESTINATION_HOST_REQUIRED")
    if parsed.username is not None or parsed.password is not None:
        raise SecureHttpError("URL_USERINFO_BLOCKED")
    if parsed.fragment:
        raise SecureHttpError("URL_FRAGMENT_BLOCKED")
    if any(host == suffix[1:] or host.endswith(suffix) for suffix in _BLOCKED_HOST_SUFFIXES):
        raise SecureHttpError("DESTINATION_HOST_BLOCKED")
    try:
        port = parsed.port or 443
    except ValueError as exc:
        raise SecureHttpError("DESTINATION_PORT_INVALID") from exc
    if port != 443:
        raise SecureHttpError("DESTINATION_PORT_BLOCKED")
    try:
        ipaddress.ip_address(host)
    except ValueError as exc:
        if "." not in host:
            raise SecureHttpError("DESTINATION_HOST_BLOCKED") from exc
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise SecureHttpError("DESTINATION_HOST_INVALID") from exc
    else:
        if not is_public_network_address(host):
            raise SecureHttpError("DESTINATION_NETWORK_BLOCKED")
    target = parsed.path or "/"
    if parsed.query:
        target = f"{target}?{parsed.query}"
    return SecureHttpsDestination(url=url, host=host, port=port, request_target=target)


def _validate_request_headers(headers: dict[str, str]) -> dict[str, str]:
    validated: dict[str, str] = {}
    for raw_name, raw_value in headers.items():
        name = str(raw_name).strip()
        value = str(raw_value)
        lowered = name.lower()
        if not _HEADER_NAME.fullmatch(name) or lowered in _BLOCKED_REQUEST_HEADERS:
            raise SecureHttpError("REQUEST_HEADER_BLOCKED")
        if "\r" in value or "\n" in value or len(value) > 8_192:
            raise SecureHttpError("REQUEST_HEADER_INVALID")
        validated[name] = value
    return validated


async def _resolve_public_addresses(host: str, port: int) -> tuple[str, ...]:
    try:
        results = await asyncio.get_running_loop().getaddrinfo(
            host,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except OSError as exc:
        raise SecureHttpError("DESTINATION_DNS_FAILED", retryable=True) from exc
    addresses = tuple(dict.fromkeys(str(item[4][0]) for item in results))
    if not addresses:
        raise SecureHttpError("DESTINATION_DNS_FAILED", retryable=True)
    if any(not is_public_network_address(address) for address in addresses):
        raise SecureHttpError("DESTINATION_NETWORK_BLOCKED")
    return addresses


async def _read_chunked_body(
    reader: asyncio.StreamReader,
    *,
    max_response_bytes: int,
) -> bytes:
    body = bytearray()
    while True:
        line = await reader.readline()
        if not line or len(line) > 128:
            raise SecureHttpError("RESPONSE_FRAMING_INVALID")
        try:
            chunk_size = int(line.split(b";", 1)[0].strip(), 16)
        except ValueError as exc:
            raise SecureHttpError("RESPONSE_FRAMING_INVALID") from exc
        if chunk_size < 0 or len(body) + chunk_size > max_response_bytes:
            raise SecureHttpError("RESPONSE_TOO_LARGE")
        if chunk_size == 0:
            while True:
                trailer = await reader.readline()
                if trailer in {b"\r\n", b""}:
                    return bytes(body)
                if len(trailer) > _MAX_HEADER_BYTES:
                    raise SecureHttpError("RESPONSE_HEADERS_TOO_LARGE")
        body.extend(await reader.readexactly(chunk_size))
        if await reader.readexactly(2) != b"\r\n":
            raise SecureHttpError("RESPONSE_FRAMING_INVALID")


async def _read_response(
    reader: asyncio.StreamReader,
    *,
    max_response_bytes: int,
) -> SecureHttpResponse:
    try:
        raw_headers = await reader.readuntil(b"\r\n\r\n")
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError) as exc:
        raise SecureHttpError("RESPONSE_HEADERS_INVALID", retryable=True) from exc
    if len(raw_headers) > _MAX_HEADER_BYTES:
        raise SecureHttpError("RESPONSE_HEADERS_TOO_LARGE")
    lines = raw_headers[:-4].split(b"\r\n")
    try:
        protocol, raw_status, *_ = lines[0].decode("ascii").split(" ")
        status_code = int(raw_status)
    except (UnicodeDecodeError, ValueError, IndexError) as exc:
        raise SecureHttpError("RESPONSE_STATUS_INVALID") from exc
    if protocol not in {"HTTP/1.0", "HTTP/1.1"} or not 100 <= status_code <= 599:
        raise SecureHttpError("RESPONSE_STATUS_INVALID")
    headers: dict[str, str] = {}
    content_lengths: set[str] = set()
    for line in lines[1:]:
        if b":" not in line:
            raise SecureHttpError("RESPONSE_HEADERS_INVALID")
        raw_name, raw_value = line.split(b":", 1)
        try:
            name = raw_name.decode("ascii").strip().lower()
            value = raw_value.decode("latin-1").strip()
        except UnicodeDecodeError as exc:
            raise SecureHttpError("RESPONSE_HEADERS_INVALID") from exc
        if not _HEADER_NAME.fullmatch(name):
            raise SecureHttpError("RESPONSE_HEADERS_INVALID")
        if name == "content-length":
            content_lengths.add(value)
        headers[name] = value
    if len(content_lengths) > 1:
        raise SecureHttpError("RESPONSE_FRAMING_INVALID")
    content_encoding = headers.get("content-encoding", "identity").lower()
    if content_encoding not in {"", "identity"}:
        raise SecureHttpError("RESPONSE_ENCODING_BLOCKED")
    transfer_encoding = headers.get("transfer-encoding", "").lower()
    if transfer_encoding:
        if transfer_encoding != "chunked" or content_lengths:
            raise SecureHttpError("RESPONSE_FRAMING_INVALID")
        body = await _read_chunked_body(reader, max_response_bytes=max_response_bytes)
    elif content_lengths:
        try:
            content_length = int(next(iter(content_lengths)))
        except ValueError as exc:
            raise SecureHttpError("RESPONSE_FRAMING_INVALID") from exc
        if content_length < 0 or content_length > max_response_bytes:
            raise SecureHttpError("RESPONSE_TOO_LARGE")
        body = await reader.readexactly(content_length)
    else:
        unframed_body = bytearray()
        while True:
            remaining = max_response_bytes - len(unframed_body)
            chunk = await reader.read(min(65_536, remaining + 1))
            if not chunk:
                break
            unframed_body.extend(chunk)
            if len(unframed_body) > max_response_bytes:
                raise SecureHttpError("RESPONSE_TOO_LARGE")
        body = bytes(unframed_body)
    if 300 <= status_code < 400:
        raise SecureHttpError("HTTP_REDIRECT_BLOCKED", status_code=status_code)
    return SecureHttpResponse(status_code=status_code, headers=headers, body=body)


async def secure_https_get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 10.0,
    max_response_bytes: int = 1_048_576,
) -> SecureHttpResponse:
    destination = validate_https_destination(url)
    addresses = await _resolve_public_addresses(destination.host, destination.port)
    safe_headers = _validate_request_headers(headers or {})
    host_header = destination.host
    if ":" in host_header:
        host_header = f"[{host_header}]"
    request_headers = {
        "Host": host_header,
        "Accept": "application/json",
        "Accept-Encoding": "identity",
        "Connection": "close",
        "User-Agent": "Orkestral-Secure-Connector/1.0",
        **safe_headers,
    }
    request = (
        f"GET {destination.request_target} HTTP/1.1\r\n"
        + "".join(f"{name}: {value}\r\n" for name, value in request_headers.items())
        + "\r\n"
    ).encode("latin-1")
    tls_context = ssl.create_default_context()
    last_error: BaseException | None = None
    for address in addresses:
        writer: asyncio.StreamWriter | None = None
        try:
            async with asyncio.timeout(timeout_seconds):
                reader, writer = await asyncio.open_connection(
                    address,
                    destination.port,
                    ssl=tls_context,
                    server_hostname=destination.host,
                )
                writer.write(request)
                await writer.drain()
                return await _read_response(
                    reader,
                    max_response_bytes=max_response_bytes,
                )
        except SecureHttpError:
            raise
        except (TimeoutError, OSError, ssl.SSLError, asyncio.IncompleteReadError) as exc:
            last_error = exc
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except (OSError, ssl.SSLError):
                    pass
    raise SecureHttpError("DESTINATION_UNAVAILABLE", retryable=True) from last_error
