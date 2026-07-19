#!/usr/bin/env bash
set -euo pipefail

required=(
  .github/workflows/ci.yml
  .github/workflows/publish-images.yml
  .github/workflows/deploy-development.yml
  .env.development.example
  .env.testing.example
  .env.staging.example
  .env.production.example
  scripts/verify-deployment.sh
)

for file in "${required[@]}"; do
  test -f "$file" || { printf 'Arquivo obrigatório ausente: %s\n' "$file" >&2; exit 1; }
done

bash -n scripts/verify-deployment.sh scripts/check-cicd-contracts.sh
rg -q 'aquasecurity/trivy-action' .github/workflows/publish-images.yml
rg -q 'actions/attest@v4' .github/workflows/publish-images.yml
rg -q 'ghcr.io' .github/workflows/publish-images.yml

for file in .env.staging.example .env.production.example; do
  if rg -n 'localhost|127\.0\.0\.1|development-only|CHANGE_ME' "$file"; then
    printf 'Contrato remoto inseguro: %s\n' "$file" >&2
    exit 1
  fi
done

printf 'Contratos CI/CD válidos.\n'
