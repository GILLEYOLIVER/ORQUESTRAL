#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
export COMPOSE_PROGRESS="${COMPOSE_PROGRESS:-plain}"

BASE_COMPOSE=(
  docker compose
  --env-file .env.example
  -f docker-compose.yml
  -f docker-compose.development.yml
)
TEST_COMPOSE=(
  docker compose
  --env-file .env.example
  -p orkestral-phase14
  -f docker-compose.yml
  -f docker-compose.development.yml
  -f docker-compose.test.yml
)
RESTORE_LOCAL=false

if [[ -n "$("${BASE_COMPOSE[@]}" ps -q 2>/dev/null || true)" ]]; then
  printf '%s\n' "Pausando temporariamente o ambiente local para liberar as portas de teste..."
  "${BASE_COMPOSE[@]}" stop
  RESTORE_LOCAL=true
fi

cleanup() {
  status=$?
  trap - EXIT INT TERM
  if [[ $status -ne 0 ]]; then
    "${TEST_COMPOSE[@]}" logs --no-color --tail=200 || true
  fi
  "${TEST_COMPOSE[@]}" down -v --remove-orphans || true
  if [[ "$RESTORE_LOCAL" == "true" ]]; then
    printf '%s\n' "Restaurando o ambiente local..."
    "${BASE_COMPOSE[@]}" up -d --wait
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

"${TEST_COMPOSE[@]}" up -d --build --wait
PHASE14_E2E=true pnpm test:e2e
