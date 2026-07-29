#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${1:-http://localhost}"
shift || true

exec uv run --project "${ROOT_DIR}/apps/api" \
  python -m app.scripts.resilience load-smoke "${BASE_URL}" "$@"
