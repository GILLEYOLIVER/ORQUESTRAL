#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_DIR="${1:-}"

if [[ -z "${BACKUP_DIR}" || ! -d "${BACKUP_DIR}" ]]; then
  printf 'Uso: CONFIRM_RESTORE=YES %s /caminho/do/backup\n' "$0" >&2
  exit 1
fi
if [[ "${CONFIRM_RESTORE:-}" != "YES" ]]; then
  printf 'Restauração cancelada. Defina CONFIRM_RESTORE=YES para confirmar.\n' >&2
  exit 1
fi
uv run --project "${ROOT_DIR}/apps/api" \
  python -m app.scripts.resilience verify-backup "${BACKUP_DIR}"

docker compose --project-directory "${ROOT_DIR}" stop api worker n8n object-storage
if [[ -f "${BACKUP_DIR}/postgres.dump" ]]; then
  docker compose --project-directory "${ROOT_DIR}" exec -T postgres \
    sh -lc 'exec pg_restore \
      --username="$POSTGRES_USER" \
      --dbname="$POSTGRES_DB" \
      --clean \
      --if-exists \
      --no-owner \
      --no-acl \
      --exit-on-error \
      --single-transaction' <"${BACKUP_DIR}/postgres.dump"
else
  gunzip -c "${BACKUP_DIR}/postgres.sql.gz" | docker compose \
    --project-directory "${ROOT_DIR}" exec -T postgres \
    sh -lc 'exec psql --set ON_ERROR_STOP=on --username="$POSTGRES_USER" postgres'
fi

for volume in object-storage-data n8n-data; do
  [[ -f "${BACKUP_DIR}/${volume}.tar.gz" ]] || continue
  docker run --rm \
    -v "orkestral_${volume}:/target" \
    -v "${BACKUP_DIR}:/backup:ro" \
    alpine:3.21 \
    sh -c "find /target -mindepth 1 -delete && tar -C /target -xzf /backup/${volume}.tar.gz"
done

docker compose --project-directory "${ROOT_DIR}" up -d
printf 'Restauração concluída. Valide health checks, auditoria e integrações.\n'
