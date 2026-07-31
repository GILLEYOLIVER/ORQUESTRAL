#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_DIR="${1:-${ROOT_DIR}/backups/$(date -u +%Y%m%dT%H%M%SZ)}"
BACKUP_SCOPE="${BACKUP_SCOPE:-full}"

if [[ "${BACKUP_SCOPE}" != "full" && "${BACKUP_SCOPE}" != "database" ]]; then
  printf 'BACKUP_SCOPE deve ser full ou database.\n' >&2
  exit 1
fi

install -d -m 700 "${BACKUP_DIR}"
database_tmp="${BACKUP_DIR}/.postgres.dump.tmp"
trap 'rm -f "${database_tmp}"' EXIT
docker compose --project-directory "${ROOT_DIR}" exec -T postgres \
  sh -lc 'exec pg_dump \
    --username="$POSTGRES_USER" \
    --dbname="$POSTGRES_DB" \
    --format=custom \
    --compress=9 \
    --no-owner \
    --no-acl' >"${database_tmp}"
mv "${database_tmp}" "${BACKUP_DIR}/postgres.dump"
chmod 600 "${BACKUP_DIR}/postgres.dump"

if [[ "${BACKUP_SCOPE}" == "full" ]]; then
  for volume in object-storage-rustfs-data n8n-data; do
    docker run --rm \
      -v "orkestral_${volume}:/source:ro" \
      -v "${BACKUP_DIR}:/backup" \
      alpine:3.21 \
      tar -C /source -czf "/backup/${volume}.tar.gz" .
    chmod 600 "${BACKUP_DIR}/${volume}.tar.gz"
  done
fi

(
  cd "${BACKUP_DIR}"
  artifacts=(postgres.dump)
  if [[ "${BACKUP_SCOPE}" == "full" ]]; then
    artifacts+=(object-storage-rustfs-data.tar.gz n8n-data.tar.gz)
  fi
  shasum -a 256 "${artifacts[@]}" >SHA256SUMS
)
chmod 600 "${BACKUP_DIR}/SHA256SUMS"
printf 'Backup concluído em %s\n' "${BACKUP_DIR}"
