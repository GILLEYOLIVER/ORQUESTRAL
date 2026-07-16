[CmdletBinding()]
param(
    [switch]$Json
)

$scriptPath = Join-Path $PSScriptRoot "infrastructure\scripts\check-environment.ps1"
& $scriptPath -Json:$Json
exit $LASTEXITCODE
