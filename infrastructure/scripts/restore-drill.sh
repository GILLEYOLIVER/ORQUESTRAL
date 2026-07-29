#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_DIR="${1:-}"

if [[ -z "${BACKUP_DIR}" || ! -d "${BACKUP_DIR}" ]]; then
  printf 'Uso: %s /caminho/do/backup\n' "$0" >&2
  exit 1
fi
uv run --project "${ROOT_DIR}/apps/api" \
  python -m app.scripts.resilience verify-backup "${BACKUP_DIR}"
if [[ ! -f "${BACKUP_DIR}/postgres.dump" ]]; then
  printf 'O drill isolado exige o formato postgres.dump atual.\n' >&2
  exit 1
fi

drill_database="orkestral_drill_$(date -u +%Y%m%d%H%M%S)_$$"
cleanup() {
  docker compose --project-directory "${ROOT_DIR}" exec -T postgres \
    sh -lc 'exec dropdb --username="$POSTGRES_USER" --if-exists "$1"' \
    sh "${drill_database}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker compose --project-directory "${ROOT_DIR}" exec -T postgres \
  sh -lc 'exec createdb --username="$POSTGRES_USER" --template=template0 "$1"' \
  sh "${drill_database}"
docker compose --project-directory "${ROOT_DIR}" exec -T postgres \
  sh -lc 'exec pg_restore \
    --username="$POSTGRES_USER" \
    --dbname="$1" \
    --no-owner \
    --no-acl \
    --exit-on-error' sh "${drill_database}" <"${BACKUP_DIR}/postgres.dump"

result="$(
  docker compose --project-directory "${ROOT_DIR}" exec -T postgres \
    sh -lc 'exec psql \
      --username="$POSTGRES_USER" \
      --dbname="$1" \
      --set=ON_ERROR_STOP=on \
      --tuples-only \
      --no-align' sh "${drill_database}" <<'SQL'
SELECT version_num FROM alembic_version LIMIT 1;
SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r';
SELECT count(*) FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relkind = 'r'
  AND c.relname <> 'marketing_public_page_registry'
  AND EXISTS (
    SELECT 1 FROM information_schema.columns column_info
    WHERE column_info.table_schema = 'public'
      AND column_info.table_name = c.relname
      AND column_info.column_name = 'company_id'
  )
  AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity);
SQL
)"
revision="$(printf '%s\n' "${result}" | sed -n '1p')"
table_count="$(printf '%s\n' "${result}" | sed -n '2p')"
rls_failures="$(printf '%s\n' "${result}" | sed -n '3p')"
table_count="${table_count:-0}"
rls_failures="${rls_failures:-1}"

if [[ -z "${revision}" || "${table_count}" -lt 1 || "${rls_failures}" -ne 0 ]]; then
  printf 'Drill inválido: revision=%s tables=%s rls_failures=%s\n' \
    "${revision}" "${table_count}" "${rls_failures}" >&2
  exit 1
fi
printf '{"status":"passed","revision":"%s","tables":%s,"rls_failures":0}\n' \
  "${revision}" "${table_count}"
