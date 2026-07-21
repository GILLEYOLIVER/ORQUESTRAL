from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from app.modules.metadata.package_lifecycle_schemas import (
    MetadataPackageManifest,
    PackageEnvironment,
)
from app.modules.metadata.package_schemas import MetadataEntityPackage

SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$")
PROMOTION_TARGETS: dict[PackageEnvironment, set[PackageEnvironment]] = {
    "local": {"development"},
    "testing": {"development"},
    "development": {"staging"},
    "staging": {"production"},
    "production": set(),
}


def parse_semver(value: str) -> tuple[int, int, int, str | None]:
    match = SEMVER_RE.fullmatch(value)
    if match is None:
        raise ValueError("Versao deve seguir SemVer, por exemplo 1.0.0.")
    prerelease = value.split("-", 1)[1] if "-" in value else None
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), prerelease


def _digest(payload: dict[str, Any]) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def calculate_bundle_checksum(
    manifest: MetadataPackageManifest,
    artifact: MetadataEntityPackage,
) -> str:
    return _digest(
        {
            "format_version": "2.0",
            "manifest": manifest.model_dump(mode="json"),
            "artifact": artifact.model_dump(mode="json"),
        }
    )


def calculate_plan_checksum(payload: dict[str, Any]) -> str:
    return _digest(payload)


def can_promote(source: PackageEnvironment, target: PackageEnvironment) -> bool:
    return target in PROMOTION_TARGETS[source]
