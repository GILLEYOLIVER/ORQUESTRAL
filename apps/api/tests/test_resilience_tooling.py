from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

import pytest

from app.scripts.resilience import (
    ProbeSample,
    ResilienceContractError,
    summarize_samples,
    validate_base_url,
    verify_backup,
)


def _write_valid_backup(root: Path) -> None:
    database = root / "postgres.dump"
    database.write_bytes(b"PGDMP" + b"\x00" * 64)
    database.chmod(0o600)
    archive = root / "object-storage-data.tar.gz"
    source = root / "document.txt"
    source.write_text("conteudo ficticio", encoding="utf-8")
    with tarfile.open(archive, "w:gz") as output:
        output.add(source, arcname="document.txt")
    source.unlink()
    archive.chmod(0o600)
    checksums = root / "SHA256SUMS"
    checksums.write_text(
        "\n".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
            for path in (database, archive)
        )
        + "\n",
        encoding="ascii",
    )
    checksums.chmod(0o600)


def test_backup_verifier_accepts_private_integral_artifacts(tmp_path: Path) -> None:
    _write_valid_backup(tmp_path)

    result = verify_backup(tmp_path)

    assert result["status"] == "verified"
    assert result["artifacts"] == ["object-storage-data.tar.gz", "postgres.dump"]


def test_backup_verifier_rejects_tampering(tmp_path: Path) -> None:
    _write_valid_backup(tmp_path)
    (tmp_path / "postgres.dump").write_bytes(b"PGDMP adulterado")

    with pytest.raises(ResilienceContractError, match="Integridade inválida"):
        verify_backup(tmp_path)


def test_load_summary_enforces_error_and_latency_budgets() -> None:
    samples = [
        ProbeSample("/health", 200, 12.0),
        ProbeSample("/ready", 200, 18.0),
        ProbeSample("/ready", 503, 20.0, "http_503"),
    ]

    report = summarize_samples(samples, max_error_rate=0.1, max_p95_ms=100.0)

    assert report["status"] == "failed"
    assert report["failures"] == 1
    assert report["error_rate"] == 0.3333


def test_load_probe_rejects_credentials_in_url() -> None:
    with pytest.raises(ResilienceContractError, match="credenciais"):
        validate_base_url("https://usuario:segredo@example.com")
