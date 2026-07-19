#!/usr/bin/env bash
set -euo pipefail

input="${1:?uso: scripts/restore-development-database.sh arquivo.dump}"
database_url="${DATABASE_URL:?defina DATABASE_URL do banco de destino}"
database_url="${database_url/postgresql+asyncpg:/postgresql:}"
[[ -f "$input" ]] || { echo "Arquivo não encontrado: $input"; exit 1; }
if command -v pg_restore >/dev/null 2>&1; then
  pg_restore --clean --if-exists --no-owner --no-acl --dbname="$database_url" "$input"
else
  docker run --rm -i -e DATABASE_URL="$database_url" postgres:18-alpine \
    sh -c 'pg_restore --clean --if-exists --no-owner --no-acl --dbname="$DATABASE_URL"' < "$input"
fi
echo "Restauração concluída. Execute a verificação de saúde antes de liberar o ambiente."
