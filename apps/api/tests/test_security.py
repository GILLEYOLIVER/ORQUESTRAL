from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.security import (
    InvalidAccessTokenError,
    WeakPasswordError,
    create_access_token,
    decode_access_token,
    hash_opaque_token,
    hash_password,
    validate_password_strength,
    verify_password,
)


def test_password_uses_argon2id_and_verifies() -> None:
    encoded = hash_password("Senha-Forte-2026!")

    assert encoded.startswith("$argon2id$")
    assert verify_password(encoded, "Senha-Forte-2026!") is True
    assert verify_password(encoded, "Senha-Incorreta-2026!") is False


@pytest.mark.parametrize(
    "password",
    ["curta!1A", "sem-maiuscula-2026!", "SEM-MINUSCULA-2026!", "SemNumero!"],
)
def test_password_policy_rejects_weak_values(password: str) -> None:
    with pytest.raises(WeakPasswordError):
        validate_password_strength(password)


def test_access_token_binds_user_session_and_company() -> None:
    settings = Settings(app_env="testing")
    user_id = uuid4()
    session_id = uuid4()
    company_id = uuid4()

    token, expires_at = create_access_token(
        settings,
        user_id=user_id,
        session_id=session_id,
        company_id=company_id,
    )
    claims = decode_access_token(settings, token)

    assert claims.user_id == user_id
    assert claims.session_id == session_id
    assert claims.company_id == company_id
    assert claims.expires_at == expires_at.replace(microsecond=0)


def test_access_token_rejects_another_secret() -> None:
    source = Settings(
        app_env="testing",
        jwt_secret="source-secret-with-at-least-32-characters",  # noqa: S106
    )
    target = Settings(
        app_env="testing",
        jwt_secret="target-secret-with-at-least-32-characters",  # noqa: S106
    )
    token, _ = create_access_token(
        source,
        user_id=uuid4(),
        session_id=uuid4(),
        company_id=None,
    )

    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(target, token)


def test_opaque_token_hash_is_keyed() -> None:
    first = Settings(app_env="testing", encryption_key="first-key-with-at-least-32-characters")
    second = Settings(app_env="testing", encryption_key="second-key-with-at-least-32-characters")

    assert hash_opaque_token(first, "refresh-token") == hash_opaque_token(first, "refresh-token")
    assert hash_opaque_token(first, "refresh-token") != hash_opaque_token(second, "refresh-token")
