from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .marketplace import (
    PackageContract,
    generate_signing_keypair,
    publisher_fingerprint,
    sign_package_contract,
    validate_package_signature,
)


def _write_protected(path: Path, value: str, *, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Arquivo já existe: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(value)
        handle.write("\n")
    path.chmod(0o600)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON deve ser um objeto: {path}")
    return value


def _keygen(args: argparse.Namespace) -> int:
    private_key, public_key = generate_signing_keypair()
    _write_protected(args.private_key, private_key, force=args.force)
    _write_protected(args.public_key, public_key, force=args.force)
    print(f"Chaves criadas. Fingerprint: {publisher_fingerprint(public_key)}")
    return 0


def _sign(args: argparse.Namespace) -> int:
    artifact_digest = hashlib.sha256(args.artifact.read_bytes()).hexdigest()
    contract = PackageContract(
        plugin_code=args.plugin_code,
        version=args.version,
        manifest=_load_json(args.manifest),
        artifact_digest=artifact_digest,
        min_platform_version=args.min_platform_version,
        max_platform_version=args.max_platform_version,
        requested_permissions=args.permission,
    )
    private_key = args.private_key.read_text(encoding="utf-8").strip()
    output = {
        "publisher_code": args.publisher_code,
        **contract.to_dict(),
        "signature": sign_package_contract(private_key, contract),
    }
    _write_protected(
        args.output,
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True),
        force=args.force,
    )
    print(f"Contrato assinado em {args.output}. Digest: {artifact_digest}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    payload = _load_json(args.contract)
    contract = PackageContract.from_dict(payload)
    signature = str(payload["signature"])
    public_key = args.public_key.read_text(encoding="utf-8").strip()
    validate_package_signature(public_key, signature, contract)
    print(f"Assinatura válida. Fingerprint: {publisher_fingerprint(public_key)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orkestral-plugin")
    commands = parser.add_subparsers(dest="command", required=True)
    keygen = commands.add_parser("keygen", help="Gerar par de chaves Ed25519")
    keygen.add_argument("--private-key", type=Path, required=True)
    keygen.add_argument("--public-key", type=Path, required=True)
    keygen.add_argument("--force", action="store_true")
    keygen.set_defaults(handler=_keygen)

    sign = commands.add_parser("sign", help="Montar e assinar contrato de pacote")
    sign.add_argument("--plugin-code", required=True)
    sign.add_argument("--publisher-code", required=True)
    sign.add_argument("--version", required=True)
    sign.add_argument("--manifest", type=Path, required=True)
    sign.add_argument("--artifact", type=Path, required=True)
    sign.add_argument("--private-key", type=Path, required=True)
    sign.add_argument("--min-platform-version", required=True)
    sign.add_argument("--max-platform-version")
    sign.add_argument("--permission", action="append", default=[])
    sign.add_argument("--output", type=Path, required=True)
    sign.add_argument("--force", action="store_true")
    sign.set_defaults(handler=_sign)

    verify = commands.add_parser("verify", help="Verificar contrato assinado")
    verify.add_argument("--contract", type=Path, required=True)
    verify.add_argument("--public-key", type=Path, required=True)
    verify.set_defaults(handler=_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))
