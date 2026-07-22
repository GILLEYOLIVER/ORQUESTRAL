#!/usr/bin/env bash
set -euo pipefail

if git ls-files | grep -E '(^|/)\.env($|\.)' | grep -Ev '\.example$' >/dev/null; then
  echo "Arquivos .env reais não podem ser versionados."
  exit 1
fi
if git grep -nE -- '-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----|sk-(live|proj)-[A-Za-z0-9_-]{16,}|github_pat_[A-Za-z0-9_]{40,}|gh[pousr]_[A-Za-z0-9]{36,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|xox[baprs]-[0-9A-Za-z-]{20,}' -- \
  ':!scripts/check-secrets.sh' ':!docs/**'; then
  echo "Possível segredo real encontrado em arquivo versionado."
  exit 1
fi
echo "Nenhum padrão conhecido de segredo real foi encontrado."
