#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

allowed_vite_keys='^(VITE_API_BASE_URL|VITE_AUTH_PREVIEW_ENABLED|VITE_N8N_ENABLED|VITE_OBJECT_STORAGE_ENABLED|VITE_REMOTE_DEVELOPMENT)$'
scan_paths=(
  apps/web/src
  apps/web/vite.config.ts
  docker-compose.yml
  docker-compose.development.yml
  .env.example
  .env.development.example
  .env.production.example
)

printf '%s\n' 'Validando a allowlist de variáveis públicas do navegador...'
while IFS= read -r key; do
  [[ -z "$key" ]] && continue
  if [[ ! "$key" =~ $allowed_vite_keys ]]; then
    printf 'Variável pública não autorizada para o frontend: %s\n' "$key" >&2
    exit 1
  fi
done < <(rg -o --no-filename 'VITE_[A-Z0-9_]+' "${scan_paths[@]}" | sort -u)

printf '%s\n' 'Validando que tokens não são persistidos no navegador...'
if rg -n -U -i \
  '(localStorage|sessionStorage)[^;]{0,180}(access.?token|refresh.?token|api.?key)|(access.?token|refresh.?token|api.?key)[^;]{0,180}(localStorage|sessionStorage)' \
  apps/web/src \
  --glob '!**/*.test.*' --glob '!**/test/**'; then
  printf '%s\n' 'Tokens ou chaves não podem ser gravados em localStorage/sessionStorage.' >&2
  exit 1
fi

if [[ -d apps/web/dist ]]; then
  printf '%s\n' 'Procurando padrões de segredo no bundle compilado...'
  if rg -n -i -- \
    '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-(live|proj)-[A-Za-z0-9_-]{16,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[0-9A-Z]{16}|xox[baprs]-[0-9A-Za-z-]{20,}' \
    apps/web/dist; then
    printf '%s\n' 'Possível segredo encontrado no bundle do navegador.' >&2
    exit 1
  fi
fi

printf '%s\n' 'Executando sonda sintética contra injeção de segredo no build...'
probe="apps/web/.env.frontend-security-probe"
probe_log="$(mktemp)"
trap 'rm -f "$probe" "$probe_log"' EXIT
printf 'VITE_API_SECRET=synthetic-browser-secret-probe\n' >"$probe"
if pnpm --dir apps/web exec vite build --mode frontend-security-probe >"$probe_log" 2>&1; then
  printf '%s\n' 'O build aceitou uma variável pública de segredo e foi bloqueado.' >&2
  exit 1
fi
if ! rg -q 'Variável pública Vite não permitida' "$probe_log"; then
  printf '%s\n' 'A sonda falhou por um motivo diferente da proteção esperada.' >&2
  exit 1
fi

printf '%s\n' 'Fronteira de segredos do frontend validada.'
