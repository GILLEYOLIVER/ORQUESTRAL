#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
CHECK_ONLY="false"
NO_START="false"

for argument in "$@"; do
  case "$argument" in
    --check-only)
      CHECK_ONLY="true"
      ;;
    --no-start)
      NO_START="true"
      ;;
    *)
      printf 'Argumento desconhecido: %s\n' "$argument" >&2
      exit 2
      ;;
  esac
done

fail() {
  printf 'Instalação interrompida: %s\n' "$1" >&2
  exit 1
}

random_hex() {
  openssl rand -hex "$1"
}

set_env_value() {
  local key="$1"
  local value="$2"
  local temporary
  temporary="$(mktemp "${ENV_FILE}.tmp.XXXXXX")"
  awk -v key="$key" -v value="$value" '
    BEGIN { found = 0 }
    index($0, key "=") == 1 {
      print key "=" value
      found = 1
      next
    }
    { print }
    END {
      if (!found) print key "=" value
    }
  ' "$ENV_FILE" >"$temporary"
  mv "$temporary" "$ENV_FILE"
}

wait_for_docker() {
  local deadline=$((SECONDS + 240))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if docker info >/dev/null 2>&1; then
      return 0
    fi
    sleep 4
  done
  return 1
}

if [ "$(uname -s)" != "Darwin" ]; then
  fail "este instalador deve ser executado no macOS"
fi
command -v openssl >/dev/null 2>&1 || fail "OpenSSL não foi encontrado"

if ! command -v docker >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    printf 'Instalando Docker Desktop pelo Homebrew...\n'
    brew install --cask docker
  else
    open "https://www.docker.com/products/docker-desktop/"
    fail "instale o Docker Desktop pela página aberta e execute novamente"
  fi
fi

if ! docker info >/dev/null 2>&1; then
  open -a Docker || true
  printf 'Aguardando o Docker Desktop iniciar...\n'
  wait_for_docker || fail "o Docker Desktop não ficou pronto em 4 minutos"
fi

docker_os="$(docker info --format '{{.OSType}}')"
[ "$docker_os" = "linux" ] || fail "o Docker deve estar usando containers Linux"

if [ "$CHECK_ONLY" = "true" ]; then
  printf 'Pré-requisitos do macOS aprovados.\n'
  exit 0
fi

credentials_created="false"
admin_password=""
if [ ! -f "$ENV_FILE" ]; then
  cp "$PROJECT_ROOT/.env.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"

  postgres_password="$(random_hex 24)"
  jwt_secret="$(random_hex 48)"
  encryption_key="$(random_hex 32)"
  monitor_secret="$(random_hex 32)"
  n8n_api_key="$(random_hex 32)"
  n8n_encryption_key="$(random_hex 32)"
  storage_user="orkestral$(random_hex 8)"
  storage_secret="$(random_hex 32)"
  admin_password="Ork-$(random_hex 16)"

  set_env_value COMPOSE_ENV_FILE ".env"
  set_env_value DATABASE_URL \
    "postgresql+asyncpg://orkestral:${postgres_password}@postgres:5432/orkestral"
  set_env_value POSTGRES_PASSWORD "$postgres_password"
  set_env_value JWT_SECRET "$jwt_secret"
  set_env_value ENCRYPTION_KEY "$encryption_key"
  set_env_value AGENT_MEMORY_MONITOR_SECRET "$monitor_secret"
  set_env_value N8N_API_KEY "$n8n_api_key"
  set_env_value N8N_ENCRYPTION_KEY "$n8n_encryption_key"
  set_env_value STORAGE_ACCESS_KEY "$storage_user"
  set_env_value MINIO_ROOT_USER "$storage_user"
  set_env_value STORAGE_SECRET_KEY "$storage_secret"
  set_env_value MINIO_ROOT_PASSWORD "$storage_secret"
  set_env_value BOOTSTRAP_ADMIN_PASSWORD "$admin_password"
  chmod 600 "$ENV_FILE"
  credentials_created="true"
else
  printf 'Configuração existente preservada: %s\n' "$ENV_FILE"
fi

if [ "$credentials_created" = "true" ]; then
  credentials_dir="$HOME/Library/Application Support/Orkestral"
  credentials_file="$credentials_dir/local-credentials.txt"
  install -d -m 700 "$credentials_dir"
  umask 077
  {
    printf 'Orkestral local\n'
    printf 'Endereço: http://localhost/login\n'
    printf 'E-mail: admin@orkestral.dev.br\n'
    printf 'Senha: %s\n' "$admin_password"
  } >"$credentials_file"
  chmod 600 "$credentials_file"
  printf 'Credenciais locais salvas com acesso privado em:\n%s\n' "$credentials_file"
fi

cat >"$HOME/Desktop/Orkestral.webloc" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>URL</key><string>http://localhost/app</string></dict></plist>
EOF

if [ "$NO_START" = "false" ]; then
  "$PROJECT_ROOT/scripts/dev.sh" start
  open "http://localhost/app"
fi
printf 'Orkestral instalado para desenvolvimento local no macOS.\n'
