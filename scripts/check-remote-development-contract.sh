#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

fail() {
  printf 'remote-development-contract: %s\n' "$1" >&2
  exit 1
}

required_files=(
  ".env.development.example"
  "Dockerfile.remote"
  "render.yaml"
  "docs/infrastructure/remote-analysis.md"
  "docs/infrastructure/provider-comparison.md"
  "docs/infrastructure/remote-development.md"
  "docs/infrastructure/deployment.md"
  "docs/infrastructure/environments.md"
  "docs/infrastructure/free-tier-limits.md"
  "docs/infrastructure/troubleshooting.md"
  "docs/infrastructure/migration.md"
  "scripts/export-development-database.sh"
  "scripts/restore-development-database.sh"
  "scripts/deploy-development-manual.sh"
  "scripts/verify-remote.sh"
)

for file in "${required_files[@]}"; do
  [[ -f "$file" ]] || fail "arquivo obrigatorio ausente: $file"
done

grep -Fq 'autoDeployTrigger: off' render.yaml || fail "auto-deploy do Render deve estar desligado"
if grep -Fq 'workflow_run:' .github/workflows/deploy-development.yml; then
  fail "deploy de desenvolvimento não pode possuir gatilho automático"
fi
grep -Fq 'release_sha:' .github/workflows/deploy-development.yml || \
  fail "workflow manual deve exigir SHA explícito"
bash -n scripts/deploy-development-manual.sh

if grep -En '(localhost|127\.0\.0\.1|host\.docker\.internal)' .env.development.example >/dev/null; then
  fail ".env.development.example contem endereco local"
fi

required_env=(
  'APP_ENV=development'
  'N8N_ENABLED=false'
  'OBJECT_STORAGE_ENABLED=false'
  'BACKGROUND_WORKER_ENABLED=false'
  'EMAIL_DELIVERY_ENABLED=false'
  'VITE_REMOTE_DEVELOPMENT=true'
  'VITE_N8N_ENABLED=false'
  'VITE_OBJECT_STORAGE_ENABLED=false'
)

for entry in "${required_env[@]}"; do
  grep -Fqx "$entry" .env.development.example || fail "variavel obrigatoria ausente: $entry"
done

required_build_args=(
  'ARG VITE_REMOTE_DEVELOPMENT=true'
  'ARG VITE_N8N_ENABLED=false'
  'ARG VITE_OBJECT_STORAGE_ENABLED=false'
)

for entry in "${required_build_args[@]}"; do
  grep -Fqx "$entry" Dockerfile.remote || fail "build remoto sem contrato: $entry"
done

printf 'remote-development-contract: ok\n'
