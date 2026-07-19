#!/usr/bin/env bash
set -euo pipefail

if git ls-files | rg '(^|/)\.env$'; then
  echo "Arquivo .env real não pode ser versionado."
  exit 1
fi
if git grep -nE -- '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-(live|proj)-[A-Za-z0-9_-]{16,}' -- \
  ':!scripts/check-secrets.sh' ':!docs/**'; then
  echo "Possível segredo real encontrado em arquivo versionado."
  exit 1
fi
echo "Nenhum padrão conhecido de segredo real foi encontrado."
