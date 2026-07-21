#!/usr/bin/env bash
set -euo pipefail

base_url="${ORKESTRAL_BASE_URL:-http://localhost}"
endpoint="${base_url%/}/health/agent-memory-scheduler"
timeout_seconds="${ORKESTRAL_MONITOR_TIMEOUT_SECONDS:-10}"
monitor_secret="${ORKESTRAL_MONITOR_SECRET:?Defina ORKESTRAL_MONITOR_SECRET no cofre do monitor}"
timestamp="$(date +%s)"
signature="$(
  ORKESTRAL_MONITOR_SECRET="$monitor_secret" \
    ORKESTRAL_MONITOR_TIMESTAMP="$timestamp" \
    python3 - <<'PY'
import hashlib
import hmac
import os

message = (
    "GET\n/health/agent-memory-scheduler\n"
    + os.environ["ORKESTRAL_MONITOR_TIMESTAMP"]
)
print(
    hmac.new(
        os.environ["ORKESTRAL_MONITOR_SECRET"].encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
)
PY
)"

if ! response="$(curl --fail-with-body --silent --show-error \
  --max-time "$timeout_seconds" \
  --header 'Accept: application/json' \
  --header "X-Orkestral-Monitor-Timestamp: $timestamp" \
  --header "X-Orkestral-Monitor-Signature: $signature" \
  "$endpoint")"; then
  printf 'Monitor do worker de memória detectou indisponibilidade em %s\n' "$endpoint" >&2
  exit 1
fi

rotation_warning="$(
  ORKESTRAL_MONITOR_RESPONSE="$response" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["ORKESTRAL_MONITOR_RESPONSE"])
if payload.get("monitor_secret_rotation_state") == "due_soon":
    days = payload.get("monitor_secret_rotation_days_remaining")
    print(f"O segredo do monitor vence em {days} dia(s); programe a rotação.")
PY
)"
if [[ -n "$rotation_warning" ]]; then
  printf 'AVISO: %s\n' "$rotation_warning" >&2
fi

printf '%s\n' "$response"
