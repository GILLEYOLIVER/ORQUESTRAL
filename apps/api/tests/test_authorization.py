from __future__ import annotations

from typing import cast

import pytest
from fastapi import HTTPException

from app.core.tenancy import Principal, require_permission
from app.modules.authentication.models import AuthSession
from app.modules.users.models import User


def _principal(*permissions: str) -> Principal:
    return Principal(
        user=cast(User, None),
        session=cast(AuthSession, None),
        company=None,
        membership=None,
        permissions=frozenset(permissions),
    )


@pytest.mark.asyncio
async def test_permission_dependency_allows_declared_permission() -> None:
    principal = _principal("agents.create")

    resolved = await require_permission("agents.create")(principal)

    assert resolved is principal


@pytest.mark.asyncio
async def test_permission_dependency_denies_missing_permission() -> None:
    with pytest.raises(HTTPException) as raised:
        await require_permission("agents.create")(_principal("agents.view"))

    assert raised.value.status_code == 403
    assert raised.value.detail == "Permissão necessária: agents.create."
