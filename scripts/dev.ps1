param(
    [ValidateSet("start", "stop", "restart", "status")]
    [string]$Action = "start",

    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = if ($env:ORKESTRAL_ENV_FILE) {
    $env:ORKESTRAL_ENV_FILE
}
elseif (Test-Path (Join-Path $ProjectRoot ".env")) {
    Join-Path $ProjectRoot ".env"
}
else {
    Join-Path $ProjectRoot ".env.example"
}
$ComposeArgs = @(
    "compose",
    "--env-file", $EnvFile,
    "-f", (Join-Path $ProjectRoot "docker-compose.yml"),
    "-f", (Join-Path $ProjectRoot "docker-compose.development.yml")
)

function Invoke-DockerCompose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    & docker @ComposeArgs @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose terminou com código $LASTEXITCODE."
    }
}

function Test-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker não foi encontrado. Instale ou abra o Docker Desktop e tente novamente."
    }

    & docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "O Docker Desktop não está pronto. Abra-o e aguarde o mecanismo iniciar."
    }
}

function Wait-Orkestral {
    param(
        [string]$Url = "http://localhost/health",
        [int]$TimeoutSeconds = 240
    )

    Write-Host "Aguardando o Orkestral ficar disponível..." -ForegroundColor Cyan
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Host "Orkestral disponível em http://localhost/app" -ForegroundColor Green
                return
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }

    Write-Host "O ambiente não ficou pronto dentro do tempo esperado." -ForegroundColor Red
    Write-Host "Últimas linhas dos serviços:" -ForegroundColor Yellow
    & docker @ComposeArgs logs --tail 80 api web nginx postgres
    throw "Falha ao iniciar o ambiente de desenvolvimento."
}

function Repair-N8nReadiness {
    & docker @ComposeArgs exec -T n8n sh -lc `
        "wget -qO- http://127.0.0.1:5678/healthz/readiness >/dev/null"
    if ($LASTEXITCODE -eq 0) {
        return
    }

    Write-Host "Reconectando o n8n aos serviços internos..." -ForegroundColor Cyan
    Invoke-DockerCompose restart n8n
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        & docker @ComposeArgs exec -T n8n sh -lc `
            "wget -qO- http://127.0.0.1:5678/healthz/readiness >/dev/null"
        if ($LASTEXITCODE -eq 0) {
            return
        }
        Start-Sleep -Seconds 3
    }
    & docker @ComposeArgs logs --tail 60 n8n postgres
    throw "O n8n não recuperou a conexão com o PostgreSQL."
}

Set-Location $ProjectRoot
Test-Docker

switch ($Action) {
    "start" {
        $upArgs = @("up", "-d")
        if (-not $NoBuild) {
            $upArgs += "--build"
        }
        Invoke-DockerCompose @upArgs
        Repair-N8nReadiness
        Wait-Orkestral
    }
    "stop" {
        Invoke-DockerCompose down
        Write-Host "Ambiente Orkestral encerrado." -ForegroundColor Green
    }
    "restart" {
        Invoke-DockerCompose down
        $upArgs = @("up", "-d")
        if (-not $NoBuild) {
            $upArgs += "--build"
        }
        Invoke-DockerCompose @upArgs
        Repair-N8nReadiness
        Wait-Orkestral
    }
    "status" {
        Invoke-DockerCompose ps
    }
}
