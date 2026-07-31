from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import stat
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

DATABASE_ARTIFACTS = frozenset({"postgres.dump", "postgres.sql.gz"})
OPTIONAL_ARCHIVES = frozenset({"object-storage-rustfs-data.tar.gz", "n8n-data.tar.gz"})
ALLOWED_ARTIFACTS = DATABASE_ARTIFACTS | OPTIONAL_ARCHIVES
DEFAULT_PROBE_PATHS = ("/health", "/ready")


class ResilienceContractError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProbeSample:
    path: str
    status_code: int
    latency_ms: float
    error: str | None = None


def _private_regular_file(root: Path, name: str) -> Path:
    candidate = root / name
    if candidate.is_symlink() or not candidate.is_file():
        raise ResilienceContractError(f"Artefato ausente ou inseguro: {name}")
    if candidate.resolve().parent != root.resolve():
        raise ResilienceContractError(f"Artefato fora do diretório: {name}")
    mode = stat.S_IMODE(candidate.stat().st_mode)
    if mode & 0o077:
        raise ResilienceContractError(f"Permissão insegura em {name}: {mode:o}")
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_checksums(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        parts = raw_line.split()
        if len(parts) != 2:
            raise ResilienceContractError(f"Checksum inválido na linha {line_number}")
        digest, raw_name = parts
        name = raw_name.removeprefix("*")
        if (
            len(digest) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in digest)
            or Path(name).name != name
            or name in checksums
        ):
            raise ResilienceContractError(f"Checksum inseguro na linha {line_number}")
        checksums[name] = digest.lower()
    return checksums


def _verify_archive(path: Path) -> None:
    with tarfile.open(path, mode="r:gz") as archive:
        for member in archive.getmembers():
            member_path = PurePosixPath(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ResilienceContractError(f"Caminho inseguro no arquivo {path.name}")


def verify_backup(directory: Path) -> dict[str, Any]:
    root = directory.expanduser().resolve()
    if not root.is_dir():
        raise ResilienceContractError("Diretório de backup inexistente")
    if stat.S_IMODE(root.stat().st_mode) & 0o077:
        raise ResilienceContractError("O diretório de backup não é privado")
    checksum_file = _private_regular_file(root, "SHA256SUMS")
    checksums = _read_checksums(checksum_file)
    names = set(checksums)
    if len(names & DATABASE_ARTIFACTS) != 1:
        raise ResilienceContractError("O backup deve conter exatamente um artefato PostgreSQL")
    if names - ALLOWED_ARTIFACTS:
        raise ResilienceContractError("O manifesto contém artefatos não autorizados")

    verified: list[str] = []
    for name, expected_digest in sorted(checksums.items()):
        artifact = _private_regular_file(root, name)
        if _sha256(artifact) != expected_digest:
            raise ResilienceContractError(f"Integridade inválida em {name}")
        if name == "postgres.dump":
            with artifact.open("rb") as stream:
                header = stream.read(5)
            if header != b"PGDMP":
                raise ResilienceContractError("postgres.dump não usa o formato custom do pg_dump")
        elif name == "postgres.sql.gz":
            with gzip.open(artifact, "rb") as stream:
                if not stream.read(1024):
                    raise ResilienceContractError("Dump PostgreSQL legado vazio")
        else:
            _verify_archive(artifact)
        verified.append(name)

    return {"status": "verified", "artifacts": verified, "count": len(verified)}


def validate_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/") + "/"
    parsed = urlparse(normalized)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ResilienceContractError("URL base inválida ou contém credenciais")
    return normalized


def _probe_once(base_url: str, path: str, timeout: float) -> ProbeSample:
    started = time.perf_counter()
    status_code = 0
    error: str | None = None
    try:
        request = Request(  # noqa: S310
            urljoin(base_url, path.lstrip("/")),
            headers={"User-Agent": "orkestral-resilience-probe/1.0"},
            method="GET",
        )
        with urlopen(request, timeout=timeout) as response:  # noqa: S310  # nosec B310
            status_code = int(response.status)
            response.read(65_536)
    except HTTPError as exc:
        status_code = int(exc.code)
        error = f"http_{status_code}"
    except (TimeoutError, URLError, OSError) as exc:
        error = type(exc).__name__.lower()
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    if not 200 <= status_code < 300 and error is None:
        error = f"http_{status_code}"
    return ProbeSample(path=path, status_code=status_code, latency_ms=latency_ms, error=error)


def summarize_samples(
    samples: list[ProbeSample],
    *,
    max_error_rate: float,
    max_p95_ms: float,
) -> dict[str, Any]:
    if not samples:
        raise ResilienceContractError("Nenhuma amostra foi produzida")
    latencies = sorted(sample.latency_ms for sample in samples)
    p95_index = max(0, math.ceil(len(latencies) * 0.95) - 1)
    failures = sum(sample.error is not None for sample in samples)
    error_rate = failures / len(samples)
    p95_ms = latencies[p95_index]
    passed = error_rate <= max_error_rate and p95_ms <= max_p95_ms
    return {
        "status": "passed" if passed else "failed",
        "requests": len(samples),
        "failures": failures,
        "error_rate": round(error_rate, 4),
        "p50_ms": latencies[(len(latencies) - 1) // 2],
        "p95_ms": p95_ms,
        "max_ms": latencies[-1],
        "thresholds": {
            "max_error_rate": max_error_rate,
            "max_p95_ms": max_p95_ms,
        },
    }


def run_load_smoke(
    base_url: str,
    *,
    request_count: int,
    concurrency: int,
    timeout: float,
    paths: tuple[str, ...] = DEFAULT_PROBE_PATHS,
    max_error_rate: float,
    max_p95_ms: float,
) -> dict[str, Any]:
    normalized_url = validate_base_url(base_url)
    if request_count < 1 or concurrency < 1 or concurrency > 100:
        raise ResilienceContractError("Quantidade ou concorrência fora dos limites")
    if not paths or any(not path.startswith("/") for path in paths):
        raise ResilienceContractError("Os caminhos do probe devem começar com /")
    with ThreadPoolExecutor(max_workers=min(concurrency, request_count)) as executor:
        futures = [
            executor.submit(_probe_once, normalized_url, paths[index % len(paths)], timeout)
            for index in range(request_count)
        ]
        samples = [future.result() for future in futures]
    report = summarize_samples(
        samples,
        max_error_rate=max_error_rate,
        max_p95_ms=max_p95_ms,
    )
    report["paths"] = list(paths)
    report["status_codes"] = {
        str(code): sum(sample.status_code == code for sample in samples)
        for code in sorted({sample.status_code for sample in samples})
    }
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ferramentas de resiliência do Orkestral")
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("verify-backup")
    backup.add_argument("directory", type=Path)
    load = commands.add_parser("load-smoke")
    load.add_argument("base_url")
    load.add_argument("--requests", type=int, default=120)
    load.add_argument("--concurrency", type=int, default=8)
    load.add_argument("--timeout", type=float, default=10.0)
    load.add_argument("--paths", default="/health,/ready")
    load.add_argument("--max-error-rate", type=float, default=0.01)
    load.add_argument("--max-p95-ms", type=float, default=1500.0)
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        if args.command == "verify-backup":
            result = verify_backup(args.directory)
        else:
            paths = tuple(path.strip() for path in args.paths.split(",") if path.strip())
            result = run_load_smoke(
                args.base_url,
                request_count=args.requests,
                concurrency=args.concurrency,
                timeout=args.timeout,
                paths=paths,
                max_error_rate=args.max_error_rate,
                max_p95_ms=args.max_p95_ms,
            )
    except ResilienceContractError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from exc
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
