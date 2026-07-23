#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

fail() {
  printf 'Database role separation contract failed: %s\n' "$1" >&2
  exit 1
}

required_files=(
  apps/api/app/core/config.py
  apps/api/app/core/resources.py
  apps/api/app/migrations/env.py
  docker-compose.yml
  .env.production.example
)
for file in "${required_files[@]}"; do
  [[ -f "$file" ]] || fail "missing contract file"
done

for key in MIGRATION_DATABASE_URL API_DATABASE_URL WORKER_DATABASE_URL; do
  rg -q "^${key}=" .env.production.example || fail "missing protected database URL"
done

rg -q '^DATABASE_ROLE_SEPARATION_REQUIRED=true$' .env.production.example ||
  fail "production does not require independent identities"
rg -q 'database_url_for\("migration"\)' apps/api/app/migrations/env.py ||
  fail "Alembic is not pinned to the migration identity"
rg -q 'database_role="api"' apps/api/app/main.py ||
  fail "API is not pinned to the runtime identity"
rg -q 'DATABASE_PROCESS_ROLE: worker' docker-compose.yml ||
  fail "worker is not pinned to its identity"

if rg -n 'VITE_(DATABASE|POSTGRES|REDIS|.*SECRET|.*TOKEN|.*API_KEY)' \
  apps/web Dockerfile.remote docker-compose.development.yml \
  --glob '!**/node_modules/**' --glob '!**/dist/**'; then
  fail "sensitive infrastructure variable crossed the browser boundary"
fi

printf 'Database role separation contract passed without exposing credentials.\n'
