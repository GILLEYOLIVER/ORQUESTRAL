from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_development_secrets() -> None:
    with pytest.raises(ValidationError, match="Valores inseguros para produção"):
        Settings(app_env="production")
