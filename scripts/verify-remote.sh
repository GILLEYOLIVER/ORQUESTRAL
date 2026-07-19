#!/usr/bin/env bash
set -euo pipefail

base_url="${1:?uso: scripts/verify-remote.sh https://servico.example [commit]}"
expected_commit="${2:-}"
health=$(curl --fail --silent --show-error --max-time 90 "$base_url/health")
ready=$(curl --fail --silent --show-error --max-time 90 "$base_url/ready")
version=$(curl --fail --silent --show-error --max-time 90 "$base_url/system/version")
printf '%s\n%s\n%s\n' "$health" "$ready" "$version"
if [[ -n "$expected_commit" ]]; then
  actual=$(printf '%s' "$version" | jq -r '.commit')
  [[ "$actual" == "$expected_commit" ]] || {
    echo "Commit remoto $actual difere de $expected_commit"
    exit 1
  }
fi
