#!/usr/bin/env bash
set -euo pipefail

base_url="${1:?usage: verify-deployment.sh URL EXPECTED_SHA [ATTEMPTS]}"
expected_sha="${2:?usage: verify-deployment.sh URL EXPECTED_SHA [ATTEMPTS]}"
attempts="${3:-80}"
base_url="${base_url%/}"

for attempt in $(seq 1 "$attempts"); do
  payload=$(curl --fail --silent --show-error --max-time 90 \
    "$base_url/system/version" || true)
  if printf '%s' "$payload" | jq -e --arg sha "$expected_sha" \
    '.commit == $sha' >/dev/null; then
    curl --fail --silent --show-error "$base_url/ready"
    printf '\nDeploy saudável no commit %s.\n' "$expected_sha"
    exit 0
  fi
  printf 'Aguardando deploy (%s/%s)...\n' "$attempt" "$attempts"
  sleep 15
done

printf 'O commit %s não ficou saudável no limite configurado.\n' "$expected_sha" >&2
exit 1
