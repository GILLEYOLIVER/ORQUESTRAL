from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.core.resources import create_resources
from app.services.readiness import ReadinessService


@pytest.mark.integration
async def test_real_postgresql_and_redis_are_ready() -> None:
    settings = get_settings()
    resources = create_resources(settings)
    try:
        report = await ReadinessService(resources, settings).run()
    finally:
        await resources.close()

    assert report.ready, report.checks
