#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash -n \
  "$ROOT_DIR/installers/macos/Install-Orkestral.command" \
  "$ROOT_DIR/scripts/dev.sh"

required_mac_markers=(
  "docker info"
  "chmod 600"
  "BOOTSTRAP_ADMIN_PASSWORD"
  "scripts/dev.sh"
)
for marker in "${required_mac_markers[@]}"; do
  rg --fixed-strings --quiet "$marker" \
    "$ROOT_DIR/installers/macos/Install-Orkestral.command"
done

required_windows_markers=(
  "RandomNumberGenerator"
  "SetAccessRuleProtection"
  "BOOTSTRAP_ADMIN_PASSWORD"
  "scripts\\dev.ps1"
)
for marker in "${required_windows_markers[@]}"; do
  rg --fixed-strings --quiet "$marker" \
    "$ROOT_DIR/installers/windows/Install-Orkestral.ps1"
done

if rg --quiet 'development-only-change-me|Orkestral-Dev-2026' \
  "$ROOT_DIR/installers/macos" "$ROOT_DIR/installers/windows"; then
  printf 'O instalador contém credencial previsível.\n' >&2
  exit 1
fi

if command -v pwsh >/dev/null 2>&1; then
  pwsh -NoProfile -Command \
    '$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile($args[0],[ref]$tokens,[ref]$errors) > $null; if ($errors.Count) { $errors | Out-String | Write-Error; exit 1 }' \
    "$ROOT_DIR/installers/windows/Install-Orkestral.ps1"
fi

printf 'Contratos dos instaladores aprovados.\n'
