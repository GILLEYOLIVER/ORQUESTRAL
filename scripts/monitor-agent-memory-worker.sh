#!/usr/bin/env bash
set -euo pipefail

base_url="${ORKESTRAL_BASE_URL:-http://localhost}"
endpoint="${base_url%/}/health/agent-memory-scheduler"
timeout_seconds="${ORKESTRAL_MONITOR_TIMEOUT_SECONDS:-10}"

if ! response="$(curl --fail-with-body --silent --show-error \
  --max-time "$timeout_seconds" \
  --header 'Accept: application/json' \
  "$endpoint")"; then
  printf 'Monitor do worker de memória detectou indisponibilidade em %s\n' "$endpoint" >&2
  exit 1
fi

printf '%s\n' "$response"
