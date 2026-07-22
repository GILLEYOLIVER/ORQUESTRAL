#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

release_sha="${1:-}"
base_url="${REMOTE_DEVELOPMENT_URL:-https://orkestral-development.onrender.com}"
: "${RENDER_DEPLOY_HOOK:?Defina RENDER_DEPLOY_HOOK apenas no ambiente do comando.}"

[[ "$RENDER_DEPLOY_HOOK" == https://api.render.com/deploy/* ]] || {
  printf 'RENDER_DEPLOY_HOOK não pertence ao endpoint HTTPS esperado do Render.\n' >&2
  exit 1
}

git fetch --quiet origin development
if [[ -z "$release_sha" ]]; then
  release_sha="$(git rev-parse origin/development)"
fi
[[ "$release_sha" =~ ^[0-9a-f]{40}$ ]] || {
  printf 'Informe um SHA completo de 40 caracteres.\n' >&2
  exit 1
}
git merge-base --is-ancestor "$release_sha" origin/development || {
  printf 'O SHA informado não pertence à branch remota development.\n' >&2
  exit 1
}

printf 'Solicitando deploy manual do commit %s.\n' "$release_sha"
curl --fail --silent --show-error --get --output /dev/null \
  --data-urlencode "ref=$release_sha" "$RENDER_DEPLOY_HOOK"
bash scripts/verify-deployment.sh "$base_url" "$release_sha"
