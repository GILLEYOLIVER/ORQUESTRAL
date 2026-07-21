from __future__ import annotations

import pytest

from app.modules.metadata.package_engine import can_promote, parse_semver


def test_semver_is_strict_and_predictable() -> None:
    assert parse_semver("2.4.1") == (2, 4, 1, None)
    assert parse_semver("1.0.0-beta.2") == (1, 0, 0, "beta.2")
    with pytest.raises(ValueError, match="SemVer"):
        parse_semver("v1.0")
    with pytest.raises(ValueError, match="SemVer"):
        parse_semver("01.0.0")


def test_promotions_follow_the_controlled_environment_path() -> None:
    assert can_promote("local", "development") is True
    assert can_promote("testing", "development") is True
    assert can_promote("development", "staging") is True
    assert can_promote("staging", "production") is True
    assert can_promote("development", "production") is False
    assert can_promote("production", "development") is False
