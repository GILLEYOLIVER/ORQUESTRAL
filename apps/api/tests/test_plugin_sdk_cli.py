from __future__ import annotations

import json
import stat
from pathlib import Path

from orkestral_plugin_sdk.cli import main


def test_cli_generates_signs_and_verifies_without_exposing_private_key(
    tmp_path: Path, capsys: object
) -> None:
    private_key = tmp_path / "publisher.key"
    public_key = tmp_path / "publisher.pub"
    manifest = tmp_path / "manifest.json"
    artifact = tmp_path / "plugin.whl"
    release = tmp_path / "release.json"
    manifest.write_text('{"dependencies": []}', encoding="utf-8")
    artifact.write_bytes(b"signed-artifact")

    assert main(
        [
            "keygen",
            "--private-key",
            str(private_key),
            "--public-key",
            str(public_key),
        ]
    ) == 0
    assert stat.S_IMODE(private_key.stat().st_mode) == 0o600
    assert main(
        [
            "sign",
            "--plugin-code",
            "crm.connector",
            "--publisher-code",
            "orkestral",
            "--version",
            "1.0.0",
            "--manifest",
            str(manifest),
            "--artifact",
            str(artifact),
            "--private-key",
            str(private_key),
            "--min-platform-version",
            "0.13.0",
            "--permission",
            "plugins.view",
            "--output",
            str(release),
        ]
    ) == 0
    assert main(
        ["verify", "--contract", str(release), "--public-key", str(public_key)]
    ) == 0
    payload = json.loads(release.read_text(encoding="utf-8"))
    assert payload["publisher_code"] == "orkestral"
    assert "private_key" not in payload
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert private_key.read_text(encoding="utf-8").strip() not in output
