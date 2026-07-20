#!/usr/bin/env bash
set -euo pipefail

required=(
  .github/workflows/ci.yml
  .github/workflows/publish-images.yml
  .github/workflows/deploy-development.yml
  .github/workflows/deploy-staging.yml
  .github/workflows/security-audit.yml
  .github/dependabot.yml
  .env.development.example
  .env.testing.example
  .env.staging.example
  .env.production.example
  scripts/verify-deployment.sh
  scripts/security-audit.sh
)

for file in "${required[@]}"; do
  test -f "$file" || { printf 'Arquivo obrigatório ausente: %s\n' "$file" >&2; exit 1; }
done

bash -n scripts/verify-deployment.sh scripts/check-cicd-contracts.sh
grep -q 'aquasecurity/trivy-action' .github/workflows/publish-images.yml
grep -q 'provenance: mode=max' .github/workflows/publish-images.yml
grep -q 'sbom: true' .github/workflows/publish-images.yml
grep -q 'imagetools inspect' .github/workflows/publish-images.yml
grep -q 'actions/workflows/ci.yml/runs' .github/workflows/publish-images.yml
grep -q 'ghcr.io' .github/workflows/publish-images.yml
grep -q 'environment: staging' .github/workflows/deploy-staging.yml
grep -q 'STAGING_MIGRATION_HOOK' .github/workflows/deploy-staging.yml
grep -q 'STAGING_ROLLBACK_HOOK' .github/workflows/deploy-staging.yml
grep -q 'verify-deployment.sh' .github/workflows/deploy-staging.yml
grep -q 'pip-audit' scripts/security-audit.sh
grep -q 'bandit' scripts/security-audit.sh
grep -q 'trivy-action' .github/workflows/security-audit.yml

for file in .env.staging.example .env.production.example; do
  if grep -nE 'localhost|127\.0\.0\.1|development-only|CHANGE_ME' "$file"; then
    printf 'Contrato remoto inseguro: %s\n' "$file" >&2
    exit 1
  fi
done

printf 'Contratos CI/CD válidos.\n'
