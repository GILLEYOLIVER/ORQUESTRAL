from __future__ import annotations

import pytest

from app.core.secure_http import (
    SecureHttpError,
    is_public_network_address,
    validate_https_destination,
)


@pytest.mark.parametrize(
    "url,code",
    [
        ("http://example.com/data", "HTTPS_REQUIRED"),
        ("https://user:secret@example.com/data", "URL_USERINFO_BLOCKED"),
        ("https://localhost/data", "DESTINATION_HOST_BLOCKED"),
        ("https://service.internal/data", "DESTINATION_HOST_BLOCKED"),
        ("https://127.0.0.1/data", "DESTINATION_NETWORK_BLOCKED"),
        ("https://169.254.169.254/latest/meta-data", "DESTINATION_NETWORK_BLOCKED"),
        ("https://example.com:8443/data", "DESTINATION_PORT_BLOCKED"),
    ],
)
def test_secure_destination_rejects_ssrf_vectors(url: str, code: str) -> None:
    with pytest.raises(SecureHttpError) as captured:
        validate_https_destination(url)
    assert captured.value.code == code


def test_secure_destination_preserves_only_safe_request_target() -> None:
    destination = validate_https_destination(
        "https://api.example.com/customers?limit=25"
    )
    assert destination.host == "api.example.com"
    assert destination.port == 443
    assert destination.request_target == "/customers?limit=25"


def test_public_network_classification_is_fail_closed() -> None:
    assert is_public_network_address("8.8.8.8")
    assert not is_public_network_address("10.0.0.10")
    assert not is_public_network_address("::1")
    assert not is_public_network_address("not-an-ip")
