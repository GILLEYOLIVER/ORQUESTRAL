import pytest
from pydantic import ValidationError

from app.modules.portals.schemas import PortalCreate
from app.modules.portals.service import create_invitation_token, hash_invitation_token


def test_invitation_persists_only_hash_contract() -> None:
    token, token_hash = create_invitation_token()
    assert token != token_hash
    assert len(token_hash) == 64
    assert hash_invitation_token(token) == token_hash


def test_portal_rejects_unknown_modules() -> None:
    with pytest.raises(ValidationError):
        PortalCreate(
            code="clientes",
            name="Clientes",
            audience="customer",
            allowed_modules=["database-admin"],
        )
