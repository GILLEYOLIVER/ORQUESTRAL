#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
BACKUP_DIR="${1:-${ROOT_DIR}/backups/$(date -u +%Y%m%dT%H%M%SZ)}"

if [[ ! -f "${ENV_FILE}" ]]; then
  printf 'Arquivo de ambiente não encontrado: %s\n' "${ENV_FILE}" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

install -d -m 700 "${BACKUP_DIR}"
docker compose --project-directory "${ROOT_DIR}" exec -T postgres \
  pg_dumpall --username="${POSTGRES_USER}" | gzip -9 >"${BACKUP_DIR}/postgres.sql.gz"
chmod 600 "${BACKUP_DIR}/postgres.sql.gz"

for volume in object-storage-data n8n-data; do
  docker run --rm \
    -v "orkestral_${volume}:/source:ro" \
    -v "${BACKUP_DIR}:/backup" \
    alpine:3.21 \
    tar -C /source -czf "/backup/${volume}.tar.gz" .
  chmod 600 "${BACKUP_DIR}/${volume}.tar.gz"
done

(
  cd "${BACKUP_DIR}"
  shasum -a 256 postgres.sql.gz object-storage-data.tar.gz n8n-data.tar.gz >SHA256SUMS
)
chmod 600 "${BACKUP_DIR}/SHA256SUMS"
printf 'Backup concluído em %s\n' "${BACKUP_DIR}"
