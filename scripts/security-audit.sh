#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

requirements="$(mktemp)"
trap 'rm -f "$requirements"' EXIT

printf '%s\n' 'Verificando segredos versionados...'
bash scripts/check-secrets.sh

printf '%s\n' 'Verificando a fronteira de segredos do frontend...'
bash scripts/check-frontend-secret-boundary.sh

printf '%s\n' 'Verificando pinning imutavel das GitHub Actions...'
unpinned="$({
  grep -REn 'uses:[[:space:]]+[^[:space:]]+@' .github/workflows || true
} | grep -Ev '@[0-9a-f]{40}([[:space:]]+#.*)?$' || true)"
if [[ -n "$unpinned" ]]; then
  printf '%s\n' "$unpinned" >&2
  printf '%s\n' 'GitHub Action sem SHA imutavel.' >&2
  exit 1
fi

printf '%s\n' 'Auditando dependencias Node de producao...'
pnpm audit --prod --audit-level high

printf '%s\n' 'Auditando codigo Python com Bandit...'
uvx --from bandit==1.9.4 bandit \
  -r apps/api/app apps/worker \
  -x apps/api/app/migrations,apps/worker/tests \
  -ll -q

printf '%s\n' 'Auditando dependencias Python de producao...'
uv export --frozen --no-dev --no-emit-workspace \
  --format requirements-txt --output-file "$requirements" >/dev/null
uvx --from pip-audit==2.10.1 pip-audit \
  --requirement "$requirements" --no-deps --disable-pip --progress-spinner off

printf '%s\n' 'Auditoria de seguranca concluida sem bloqueios.'
