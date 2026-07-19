#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

fail() {
  printf 'Production readiness contract failed: %s\n' "$1" >&2
  exit 1
}

required_files=(
  .env.production.example
  .github/workflows/deploy-production.yml
  docs/infrastructure/production.md
  scripts/verify-deployment.sh
)
for file in "${required_files[@]}"; do
  [[ -f "$file" ]] || fail "missing $file"
done

workflow_markers=(
  "name: production"
  "PROMOVER-PRODUCAO"
  "Verify immutable images and provenance"
  "Create pre-change backup"
  "Run database migration task"
  "Automatically restore last known-good release"
  "scripts/verify-deployment.sh"
  "PRODUCTION_HOOK_TOKEN"
)
for marker in "${workflow_markers[@]}"; do
  rg --fixed-strings --quiet "$marker" .github/workflows/deploy-production.yml ||
    fail "workflow marker not found: $marker"
done

environment_keys=(
  APP_ENV
  DATABASE_URL
  REDIS_URL
  JWT_SECRET
  ENCRYPTION_KEY
  CORS_ORIGINS
  BILLING_ENFORCEMENT_ENABLED
  KNOWLEDGE_EMBEDDING_PROVIDER
  RUN_MIGRATIONS_ON_STARTUP
  BOOTSTRAP_ENABLED
  VITE_AUTH_PREVIEW_ENABLED
)
for key in "${environment_keys[@]}"; do
  rg --regexp "^${key}=" --quiet .env.production.example ||
    fail "environment key not found: $key"
done

rg --fixed-strings --quiet "APP_ENV=production" .env.production.example ||
  fail "APP_ENV must be production"
rg --fixed-strings --quiet "BILLING_ENFORCEMENT_ENABLED=true" .env.production.example ||
  fail "billing enforcement must be enabled"
rg --fixed-strings --quiet "KNOWLEDGE_EMBEDDING_PROVIDER=openai_compatible" .env.production.example ||
  fail "production embeddings must use the external provider"
rg --fixed-strings --quiet "RUN_MIGRATIONS_ON_STARTUP=false" .env.production.example ||
  fail "replicas must not run migrations on startup"
rg --fixed-strings --quiet "BOOTSTRAP_ENABLED=false" .env.production.example ||
  fail "bootstrap must be disabled"
rg --fixed-strings --quiet "VITE_AUTH_PREVIEW_ENABLED=false" .env.production.example ||
  fail "authentication preview must be disabled"

if rg --regexp '^[A-Z0-9_]+=.*(localhost|127\.0\.0\.1|development-only|change-me)' \
  .env.production.example; then
  fail "unsafe local or sample value found in production environment"
fi

printf 'Production readiness contract passed.\n'
