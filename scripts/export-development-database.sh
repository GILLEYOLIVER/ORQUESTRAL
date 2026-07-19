#!/usr/bin/env bash
set -euo pipefail

output="${1:-orkestral-development-$(date -u +%Y%m%dT%H%M%SZ).dump}"
database_url="${DATABASE_URL:?defina DATABASE_URL sem registrá-la no shell compartilhado}"
database_url="${database_url/postgresql+asyncpg:/postgresql:}"
[[ ! -e "$output" ]] || { echo "O arquivo $output já existe."; exit 1; }
umask 077
if command -v pg_dump >/dev/null 2>&1; then
  pg_dump --no-owner --no-acl --format=custom "$database_url" > "$output"
else
  docker run --rm -e DATABASE_URL="$database_url" postgres:18-alpine \
    sh -c 'pg_dump --no-owner --no-acl --format=custom "$DATABASE_URL"' > "$output"
fi
echo "Exportação criada em $output. Trate-a como dado pessoal e mantenha-a fora do Git."
