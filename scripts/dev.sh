#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-start}"
NO_BUILD="false"

shift || true
while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-build | -n)
      NO_BUILD="true"
      ;;
    *)
      echo "Argumento desconhecido: $1" >&2
      exit 2
      ;;
  esac
  shift
done

case "$ACTION" in
  start | stop | restart | status)
    ;;
  *)
    echo "Acao invalida: $ACTION" >&2
    echo "Use: $0 [start|stop|restart|status] [--no-build]" >&2
    exit 2
    ;;
esac

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
COMPOSE_ARGS=(
  compose
  --env-file "$PROJECT_ROOT/.env.example"
  -f "$PROJECT_ROOT/docker-compose.yml"
  -f "$PROJECT_ROOT/docker-compose.development.yml"
)

run_compose() {
  docker "${COMPOSE_ARGS[@]}" "$@"
}

test_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker nao foi encontrado no PATH." >&2
    if [ "$(uname -s)" = "Darwin" ]; then
      echo "Instale o Docker Desktop para macOS e abra o aplicativo antes de pressionar F5." >&2
    else
      echo "Instale o Docker Engine com Docker Compose v2 e tente novamente." >&2
    fi
    exit 1
  fi

  if ! docker info >/dev/null 2>&1; then
    echo "Docker esta instalado, mas o engine nao esta pronto." >&2
    if [ "$(uname -s)" = "Darwin" ]; then
      echo "Abra o Docker Desktop e aguarde o status Running antes de pressionar F5." >&2
    else
      echo "Inicie o servico do Docker e tente novamente." >&2
    fi
    exit 1
  fi
}

wait_orkestral() {
  local url="${1:-http://localhost/health}"
  local timeout_seconds="${2:-240}"
  local deadline=$((SECONDS + timeout_seconds))

  echo "Aguardando o Orkestral ficar disponivel..."
  while [ "$SECONDS" -lt "$deadline" ]; do
    if curl --fail --silent --show-error --max-time 5 "$url" >/dev/null 2>&1; then
      echo "Orkestral disponivel em http://localhost/app"
      return 0
    fi
    sleep 2
  done

  echo "O ambiente nao ficou pronto dentro do tempo esperado." >&2
  echo "Ultimas linhas dos servicos:" >&2
  run_compose logs --tail 80 api web nginx postgres >&2 || true
  echo "Falha ao iniciar o ambiente de desenvolvimento." >&2
  exit 1
}

cd "$PROJECT_ROOT"
test_docker

case "$ACTION" in
  start)
    UP_ARGS=(up -d)
    if [ "$NO_BUILD" != "true" ]; then
      UP_ARGS+=(--build)
    fi
    run_compose "${UP_ARGS[@]}"
    wait_orkestral
    ;;
  stop)
    run_compose down
    echo "Ambiente Orkestral encerrado."
    ;;
  restart)
    run_compose down
    UP_ARGS=(up -d)
    if [ "$NO_BUILD" != "true" ]; then
      UP_ARGS+=(--build)
    fi
    run_compose "${UP_ARGS[@]}"
    wait_orkestral
    ;;
  status)
    run_compose ps
    ;;
esac
