[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$EnvFile = Join-Path $ProjectRoot ".env"

function New-RandomHex {
    param([int]$Bytes)
    $buffer = New-Object byte[] $Bytes
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($buffer)
    }
    finally {
        $generator.Dispose()
    }
    return -join ($buffer | ForEach-Object { $_.ToString("x2") })
}

function Set-EnvValue {
    param(
        [string]$Key,
        [string]$Value
    )
    $lines = [System.IO.File]::ReadAllLines($EnvFile)
    $found = $false
    for ($index = 0; $index -lt $lines.Length; $index++) {
        if ($lines[$index].StartsWith("$Key=")) {
            $lines[$index] = "$Key=$Value"
            $found = $true
            break
        }
    }
    if (-not $found) {
        $lines += "$Key=$Value"
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($EnvFile, (($lines -join "`n") + "`n"), $utf8)
}

function Wait-Docker {
    $deadline = (Get-Date).AddMinutes(4)
    while ((Get-Date) -lt $deadline) {
        & docker info *> $null
        if ($LASTEXITCODE -eq 0) {
            return
        }
        Start-Sleep -Seconds 4
    }
    throw "O Docker Desktop não ficou pronto em 4 minutos."
}

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq "Core") {
    throw "Este instalador deve ser executado no Windows."
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Instalando Docker Desktop pelo winget..." -ForegroundColor Cyan
        & winget install --exact --id Docker.DockerDesktop --accept-package-agreements `
            --accept-source-agreements
        if ($LASTEXITCODE -ne 0) {
            throw "O winget não conseguiu instalar o Docker Desktop."
        }
        $dockerBin = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"
        $env:Path = "$dockerBin;$env:Path"
    }
    else {
        Start-Process "https://www.docker.com/products/docker-desktop/"
        throw "Instale o Docker Desktop pela página aberta e execute novamente."
    }
}

& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $desktop = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path $desktop) {
        Start-Process $desktop
    }
    Write-Host "Aguardando o Docker Desktop iniciar..." -ForegroundColor Cyan
    Wait-Docker
}

$dockerOs = (& docker info --format "{{.OSType}}").Trim()
if ($dockerOs -ne "linux") {
    throw "O Docker Desktop deve estar configurado para containers Linux."
}

if ($CheckOnly) {
    Write-Host "Pré-requisitos do Windows aprovados." -ForegroundColor Green
    exit 0
}

$credentialsCreated = $false
$adminPassword = ""
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $ProjectRoot ".env.example") $EnvFile

    $postgresPassword = New-RandomHex 24
    $jwtSecret = New-RandomHex 48
    $encryptionKey = New-RandomHex 32
    $monitorSecret = New-RandomHex 32
    $n8nApiKey = New-RandomHex 32
    $n8nEncryptionKey = New-RandomHex 32
    $storageUser = "orkestral$(New-RandomHex 8)"
    $storageSecret = New-RandomHex 32
    $adminPassword = "Ork-$(New-RandomHex 16)"

    Set-EnvValue "COMPOSE_ENV_FILE" ".env"
    Set-EnvValue "DATABASE_URL" `
        "postgresql+asyncpg://orkestral:${postgresPassword}@postgres:5432/orkestral"
    Set-EnvValue "POSTGRES_PASSWORD" $postgresPassword
    Set-EnvValue "JWT_SECRET" $jwtSecret
    Set-EnvValue "ENCRYPTION_KEY" $encryptionKey
    Set-EnvValue "AGENT_MEMORY_MONITOR_SECRET" $monitorSecret
    Set-EnvValue "N8N_API_KEY" $n8nApiKey
    Set-EnvValue "N8N_ENCRYPTION_KEY" $n8nEncryptionKey
    Set-EnvValue "STORAGE_ACCESS_KEY" $storageUser
    Set-EnvValue "MINIO_ROOT_USER" $storageUser
    Set-EnvValue "STORAGE_SECRET_KEY" $storageSecret
    Set-EnvValue "MINIO_ROOT_PASSWORD" $storageSecret
    Set-EnvValue "BOOTSTRAP_ADMIN_PASSWORD" $adminPassword
    $credentialsCreated = $true
}
else {
    Write-Host "Configuração existente preservada: $EnvFile" -ForegroundColor Yellow
}

if ($credentialsCreated) {
    $credentialsDir = Join-Path $env:LOCALAPPDATA "Orkestral"
    $credentialsFile = Join-Path $credentialsDir "local-credentials.txt"
    New-Item -ItemType Directory -Force -Path $credentialsDir | Out-Null
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $acl = New-Object System.Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $identity,
        "FullControl",
        "ContainerInherit,ObjectInherit",
        "None",
        "Allow"
    )
    $acl.AddAccessRule($rule)
    Set-Acl -Path $credentialsDir -AclObject $acl
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $content = @(
        "Orkestral local",
        "Endereço: http://localhost/login",
        "E-mail: admin@orkestral.dev.br",
        "Senha: $adminPassword"
    ) -join "`r`n"
    [System.IO.File]::WriteAllText($credentialsFile, "$content`r`n", $utf8)
    Write-Host "Credenciais locais salvas com acesso privado em:`n$credentialsFile"
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcut = Join-Path $desktop "Orkestral.url"
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText(
    $shortcut,
    "[InternetShortcut]`r`nURL=http://localhost/app`r`n",
    $utf8
)

if (-not $NoStart) {
    & (Join-Path $ProjectRoot "scripts\dev.ps1") start
    Start-Process "http://localhost/app"
}
Write-Host "Orkestral instalado para desenvolvimento local no Windows." `
    -ForegroundColor Green
