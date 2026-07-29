from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.identity.schemas import IdentityProviderCreate
from app.modules.identity.service import create_scim_token, parse_scim_token


def test_scim_token_encodes_only_routing_ids_and_entropy() -> None:
    company_id = uuid4()
    token_id = uuid4()
    token = create_scim_token(company_id, token_id)
    parsed = parse_scim_token(token)
    assert parsed.company_id == company_id
    assert parsed.token_id == token_id
    assert len(token.split(".")[3]) >= 48


def test_scim_token_rejects_invalid_contract() -> None:
    with pytest.raises(ValueError, match="inválido"):
        parse_scim_token("scim.invalid")


def test_oidc_configuration_requires_all_security_endpoints() -> None:
    with pytest.raises(ValidationError, match="OIDC exige"):
        IdentityProviderCreate.model_validate(
            {
                "code": "corporativo",
                "name": "Corporativo",
                "provider_type": "oidc",
                "issuer": "https://id.example.com",
                "client_id": "client",
            }
        )
