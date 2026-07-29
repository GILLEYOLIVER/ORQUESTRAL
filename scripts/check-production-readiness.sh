#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

fail() {
  printf 'Production readiness contract failed: %s\n' "$1" >&2
  exit 1
}

contains_fixed() {
  if command -v rg >/dev/null 2>&1; then
    rg --fixed-strings --quiet "$1" "$2"
  else
    grep --fixed-strings --quiet -- "$1" "$2"
  fi
}

contains_regex() {
  if command -v rg >/dev/null 2>&1; then
    rg --regexp "$1" --quiet "$2"
  else
    grep --extended-regexp --quiet -- "$1" "$2"
  fi
}

required_files=(
  .env.production.example
  .github/workflows/deploy-production.yml
  docs/ORKESTRAL_DISASTER_RECOVERY.md
  docs/ORKESTRAL_ENTERPRISE_OPERATIONS.md
  docs/infrastructure/production.md
  infrastructure/scripts/restore-drill.sh
  scripts/load-smoke.sh
  scripts/verify-deployment.sh
)
for file in "${required_files[@]}"; do
  [[ -f "$file" ]] || fail "missing $file"
done

for script in infrastructure/scripts/restore-drill.sh scripts/load-smoke.sh; do
  [[ -x "$script" ]] || fail "script is not executable: $script"
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
  contains_fixed "$marker" .github/workflows/deploy-production.yml ||
    fail "workflow marker not found: $marker"
done

environment_keys=(
  APP_ENV
  DATABASE_URL
  MIGRATION_DATABASE_URL
  API_DATABASE_URL
  WORKER_DATABASE_URL
  DATABASE_ROLE_SEPARATION_REQUIRED
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
  contains_regex "^${key}=" .env.production.example ||
    fail "environment key not found: $key"
done

contains_fixed "APP_ENV=production" .env.production.example ||
  fail "APP_ENV must be production"
contains_fixed "DATABASE_ROLE_SEPARATION_REQUIRED=true" .env.production.example ||
  fail "database role separation must be required"
contains_fixed "BILLING_ENFORCEMENT_ENABLED=true" .env.production.example ||
  fail "billing enforcement must be enabled"
contains_fixed "KNOWLEDGE_EMBEDDING_PROVIDER=openai_compatible" .env.production.example ||
  fail "production embeddings must use the external provider"
contains_fixed "RUN_MIGRATIONS_ON_STARTUP=false" .env.production.example ||
  fail "replicas must not run migrations on startup"
contains_fixed "BOOTSTRAP_ENABLED=false" .env.production.example ||
  fail "bootstrap must be disabled"
contains_fixed "VITE_AUTH_PREVIEW_ENABLED=false" .env.production.example ||
  fail "authentication preview must be disabled"

if contains_regex '^[A-Z0-9_]+=.*(localhost|127\.0\.0\.1|development-only|change-me)' \
  .env.production.example; then
  fail "unsafe local or sample value found in production environment"
fi

printf 'Production readiness contract passed.\n'
