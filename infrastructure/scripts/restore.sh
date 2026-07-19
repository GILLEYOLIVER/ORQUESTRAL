#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
BACKUP_DIR="${1:-}"

if [[ -z "${BACKUP_DIR}" || ! -d "${BACKUP_DIR}" ]]; then
  printf 'Uso: CONFIRM_RESTORE=YES %s /caminho/do/backup\n' "$0" >&2
  exit 1
fi
if [[ "${CONFIRM_RESTORE:-}" != "YES" ]]; then
  printf 'Restauração cancelada. Defina CONFIRM_RESTORE=YES para confirmar.\n' >&2
  exit 1
fi
if [[ ! -f "${ENV_FILE}" ]]; then
  printf 'Arquivo de ambiente não encontrado: %s\n' "${ENV_FILE}" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

(
  cd "${BACKUP_DIR}"
  shasum -a 256 -c SHA256SUMS
)

docker compose --project-directory "${ROOT_DIR}" stop api worker n8n object-storage
gunzip -c "${BACKUP_DIR}/postgres.sql.gz" | docker compose \
  --project-directory "${ROOT_DIR}" exec -T postgres \
  psql --set ON_ERROR_STOP=on --username="${POSTGRES_USER}" postgres

for volume in object-storage-data n8n-data; do
  docker run --rm \
    -v "orkestral_${volume}:/target" \
    -v "${BACKUP_DIR}:/backup:ro" \
    alpine:3.21 \
    sh -c "find /target -mindepth 1 -delete && tar -C /target -xzf /backup/${volume}.tar.gz"
done

docker compose --project-directory "${ROOT_DIR}" up -d
printf 'Restauração concluída. Valide health checks, auditoria e integrações.\n'
