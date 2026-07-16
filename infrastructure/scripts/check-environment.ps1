[CmdletBinding()]
param(
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Terminais abertos antes de uma instalação mantêm uma cópia antiga do PATH.
# Recarregue os valores persistidos no Windows sem exigir que o VS Code seja fechado.
$pathSources = @(
    [Environment]::GetEnvironmentVariable("Path", "User"),
    [Environment]::GetEnvironmentVariable("Path", "Machine"),
    $env:Path
)
$seenPaths = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$pathEntries = foreach ($source in $pathSources) {
    if ([string]::IsNullOrWhiteSpace($source)) {
        continue
    }

    foreach ($entry in [Environment]::ExpandEnvironmentVariables($source).Split(";")) {
        $cleanEntry = $entry.Trim()
        if ([string]::IsNullOrWhiteSpace($cleanEntry) -or $cleanEntry -match '^\$\(') {
            continue
        }
        if ($seenPaths.Add($cleanEntry)) {
            $cleanEntry
        }
    }
}
$env:Path = $pathEntries -join ";"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$checks = [System.Collections.Generic.List[object]]::new()
$warnings = [System.Collections.Generic.List[string]]::new()

function Add-Check {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [bool]$Success,
        [Parameter(Mandatory)] [string]$Detail,
        [string]$Fix = "",
        [bool]$Required = $true
    )

    $checks.Add([PSCustomObject]@{
        name     = $Name
        success  = $Success
        required = $Required
        detail   = $Detail
        fix      = $Fix
    })
}

function Convert-ToVersion {
    param([string]$Text)

    $match = [regex]::Match($Text, "(?<major>\d+)\.(?<minor>\d+)(?:\.(?<patch>\d+))?")
    if (-not $match.Success) {
        return $null
    }

    $patch = if ($match.Groups["patch"].Success) { $match.Groups["patch"].Value } else { "0" }
    return [version]::new(
        [int]$match.Groups["major"].Value,
        [int]$match.Groups["minor"].Value,
        [int]$patch
    )
}

function Get-CommandOutput {
    param(
        [Parameter(Mandatory)] [string]$Command,
        [string[]]$Arguments = @()
    )

    $resolved = Get-Command $Command -ErrorAction SilentlyContinue
    if ($null -eq $resolved) {
        return [PSCustomObject]@{ Found = $false; ExitCode = -1; Output = ""; Path = "" }
    }

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $outputItems = @(& $resolved.Source @Arguments 2>&1)
        $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
        $outputLines = foreach ($item in $outputItems) {
            if ($item -is [System.Management.Automation.ErrorRecord]) {
                $item.Exception.Message
            }
            else {
                [string]$item
            }
        }
        $output = (($outputLines -join [Environment]::NewLine) -replace "`0", "").Trim()
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }

    return [PSCustomObject]@{
        Found    = $true
        ExitCode = $exitCode
        Output   = $output
        Path     = $resolved.Source
    }
}

function Test-VersionedCommand {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$Command,
        [string[]]$Arguments = @("--version"),
        [Parameter(Mandatory)] [version]$MinimumVersion,
        [Parameter(Mandatory)] [string]$Fix,
        [bool]$Required = $true
    )

    $result = Get-CommandOutput -Command $Command -Arguments $Arguments
    if (-not $result.Found) {
        Add-Check -Name $Name -Success $false -Detail "Não encontrado no PATH." -Fix $Fix -Required $Required
        return
    }

    $version = Convert-ToVersion -Text $result.Output
    if ($null -eq $version) {
        Add-Check -Name $Name -Success $false -Detail "Instalado, mas a versão não pôde ser identificada: $($result.Output)" -Fix $Fix -Required $Required
        return
    }

    $supported = $version -ge $MinimumVersion
    $detail = "Versão $version em $($result.Path)"
    if (-not $supported) {
        $detail += "; mínimo exigido: $MinimumVersion"
    }
    Add-Check -Name $Name -Success $supported -Detail $detail -Fix $Fix -Required $Required
}

function Test-ProjectFile {
    param(
        [Parameter(Mandatory)] [string]$RelativePath,
        [Parameter(Mandatory)] [string]$Description
    )

    $path = Join-Path $projectRoot $RelativePath
    $parameters = @{
        Name    = $Description
        Success = (Test-Path -LiteralPath $path)
        Detail  = $(if (Test-Path -LiteralPath $path) { $RelativePath } else { "Arquivo ausente: $RelativePath" })
        Fix     = "Restaure o arquivo do repositório."
    }
    Add-Check @parameters
}

# Sistema operacional e virtualização
$os = Get-CimInstance Win32_OperatingSystem
Add-Check -Name "Windows 64 bits" -Success ($os.OSArchitecture -like "*64*") -Detail "$($os.Caption), build $($os.BuildNumber), $($os.OSArchitecture)" -Fix "Use Windows 10/11 de 64 bits compatível com WSL 2."

$processor = Get-CimInstance Win32_Processor | Select-Object -First 1
$computerSystem = Get-CimInstance Win32_ComputerSystem
$virtualizationEnabled = [bool]$processor.VirtualizationFirmwareEnabled -or [bool]$computerSystem.HypervisorPresent
$virtualizationDetail = if ($computerSystem.HypervisorPresent) {
    "Hypervisor do Windows ativo; Intel VT-x/AMD-V disponível."
}
elseif ($processor.VirtualizationFirmwareEnabled) {
    "Intel VT-x/AMD-V habilitado."
}
else {
    "Virtualização não detectada."
}
Add-Check -Name "Virtualização no firmware" -Success $virtualizationEnabled -Detail $virtualizationDetail -Fix "Habilite Intel VT-x/AMD-V na BIOS/UEFI."

# Ferramentas principais
Test-VersionedCommand -Name "Git" -Command "git" -MinimumVersion ([version]"2.40.0") -Fix "winget install --exact --id Git.Git"
Test-VersionedCommand -Name "Node.js" -Command "node" -MinimumVersion ([version]"24.0.0") -Fix "winget install --exact --id OpenJS.NodeJS.LTS --source winget"
Test-VersionedCommand -Name "npm" -Command "npm" -MinimumVersion ([version]"11.0.0") -Fix "O npm é instalado junto com o Node.js 24 LTS."
Test-VersionedCommand -Name "pnpm" -Command "pnpm" -MinimumVersion ([version]"11.0.0") -Fix "npm install --global pnpm@11.7.0"
Test-VersionedCommand -Name "uv" -Command "uv" -MinimumVersion ([version]"0.11.0") -Fix "python -m pip install uv==0.11.29"

# Ambiente Python do projeto
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPython) {
    $pythonOutput = (& $venvPython --version 2>&1 | Out-String).Trim()
    $pythonVersion = Convert-ToVersion -Text $pythonOutput
    $pythonOk = $null -ne $pythonVersion -and $pythonVersion -ge [version]"3.13.0" -and $pythonVersion -lt [version]"3.14.0"
    Add-Check -Name "Python da .venv" -Success $pythonOk -Detail "$pythonOutput em $venvPython" -Fix "uv sync --all-packages --all-extras"

    $pytestOutput = (& $venvPython -m pytest --version 2>&1 | Out-String).Trim()
    Add-Check -Name "Dependências Python" -Success ($LASTEXITCODE -eq 0) -Detail $(if ($LASTEXITCODE -eq 0) { $pytestOutput } else { "pytest não está disponível na .venv." }) -Fix "uv sync --all-packages --all-extras"
}
else {
    Add-Check -Name "Python da .venv" -Success $false -Detail ".venv não encontrada." -Fix "uv sync --all-packages --all-extras"
    Add-Check -Name "Dependências Python" -Success $false -Detail "Não verificadas porque a .venv não existe." -Fix "uv sync --all-packages --all-extras"
}

# WSL 2
$wslResult = Get-CommandOutput -Command "wsl" -Arguments @("--version")
$wslVersion = Convert-ToVersion -Text $wslResult.Output
$wslOk = $wslResult.Found -and $wslResult.ExitCode -eq 0 -and $null -ne $wslVersion -and $wslVersion -ge [version]"2.1.5"
$wslDetail = if ($wslOk) { "WSL $wslVersion" } elseif ($wslResult.Found) { "WSL 2 não está instalado ou não atende à versão mínima 2.1.5." } else { "WSL não encontrado." }
Add-Check -Name "WSL 2" -Success $wslOk -Detail $wslDetail -Fix "Em PowerShell como administrador: wsl --install; reinicie; depois execute wsl --update."

# Docker CLI, Compose e engine
$dockerCommand = Get-CommandOutput -Command "docker" -Arguments @("--version")
$dockerVersion = Convert-ToVersion -Text $dockerCommand.Output
$dockerCliOk = $dockerCommand.Found -and $dockerCommand.ExitCode -eq 0 -and $null -ne $dockerVersion
Add-Check -Name "Docker CLI" -Success $dockerCliOk -Detail $(if ($dockerCliOk) { $dockerCommand.Output } else { "Docker não encontrado no PATH." }) -Fix "winget install --exact --id Docker.DockerDesktop"

if ($dockerCliOk) {
    $composeResult = Get-CommandOutput -Command "docker" -Arguments @("compose", "version", "--short")
    $composeVersion = Convert-ToVersion -Text $composeResult.Output
    $composeOk = $composeResult.ExitCode -eq 0 -and $null -ne $composeVersion -and $composeVersion -ge [version]"2.20.0"
    Add-Check -Name "Docker Compose" -Success $composeOk -Detail $(if ($composeOk) { "Versão $composeVersion" } else { "Compose v2 não disponível." }) -Fix "Atualize o Docker Desktop."

    $desktopStatus = Get-CommandOutput -Command "docker" -Arguments @("desktop", "status")
    $desktopStopped = $desktopStatus.ExitCode -eq 0 -and $desktopStatus.Output -match '(?i)\bStatus\s+stopped\b'

    if ($desktopStopped) {
        $engineOk = $false
        $engineVersion = ""
    }
    else {
        $engineResult = Get-CommandOutput -Command "docker" -Arguments @("info", "--format", "{{.ServerVersion}}")
        $engineVersion = $engineResult.Output.Trim()
        $engineOk = $engineResult.ExitCode -eq 0 -and $engineVersion -match '^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$'
    }

    Add-Check -Name "Docker Engine" -Success $engineOk -Detail $(if ($engineOk) { "Engine ativo, versão $engineVersion." } else { "Docker Desktop instalado, mas o engine Linux não está ativo." }) -Fix "Reinicie o Windows, abra o Docker Desktop e aguarde o status Running."
}
else {
    Add-Check -Name "Docker Compose" -Success $false -Detail "Não verificado porque o Docker CLI está ausente." -Fix "Instale o Docker Desktop."
    Add-Check -Name "Docker Engine" -Success $false -Detail "Não verificado porque o Docker CLI está ausente." -Fix "Instale e inicie o Docker Desktop."
}

# Arquivos e dependências do repositório
Test-ProjectFile -RelativePath "pyproject.toml" -Description "Workspace Python"
Test-ProjectFile -RelativePath "uv.lock" -Description "Lockfile Python"
Test-ProjectFile -RelativePath "package.json" -Description "Workspace Node"
Test-ProjectFile -RelativePath "pnpm-lock.yaml" -Description "Lockfile Node"
Test-ProjectFile -RelativePath ".env.example" -Description "Variáveis de exemplo"
Test-ProjectFile -RelativePath "docker-compose.yml" -Description "Compose base"
Test-ProjectFile -RelativePath "docker-compose.development.yml" -Description "Compose de desenvolvimento"

$nodeModules = Join-Path $projectRoot "node_modules"
Add-Check -Name "Dependências Node" -Success (Test-Path -LiteralPath $nodeModules) -Detail $(if (Test-Path -LiteralPath $nodeModules) { "node_modules presente." } else { "node_modules ausente." }) -Fix "pnpm install --frozen-lockfile"

# Portas: informativas, pois podem estar ocupadas pela própria Orkestral.
$projectPorts = @(80, 5173, 8000, 5432, 15432, 5678, 6379, 9000, 9001)
foreach ($port in $projectPorts) {
    $connections = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
    if ($connections.Count -gt 0) {
        $ownerIds = @($connections | Select-Object -ExpandProperty OwningProcess -Unique)
        $processDescriptions = foreach ($ownerId in $ownerIds) {
            $process = Get-Process -Id $ownerId -ErrorAction SilentlyContinue
            if ($null -ne $process) { "$($process.ProcessName) (PID $($process.Id))" } else { "PID $ownerId" }
        }
        $warnings.Add("Porta $port ocupada por $($processDescriptions -join ', ').")
    }
}

$requiredFailures = @($checks | Where-Object { $_.required -and -not $_.success })
$allRequiredOk = $requiredFailures.Count -eq 0

if ($Json) {
    [PSCustomObject]@{
        project_root = $projectRoot
        ready        = $allRequiredOk
        checks       = $checks
        warnings     = $warnings
    } | ConvertTo-Json -Depth 5
}
else {
    Write-Host ""
    Write-Host "ORKESTRAL - VERIFICAÇÃO DO AMBIENTE" -ForegroundColor Cyan
    Write-Host "Projeto: $projectRoot"
    Write-Host ""

    foreach ($check in $checks) {
        if ($check.success) {
            Write-Host "[OK]    " -ForegroundColor Green -NoNewline
            Write-Host "$($check.name): $($check.detail)"
        }
        elseif ($check.required) {
            Write-Host "[FALTA] " -ForegroundColor Red -NoNewline
            Write-Host "$($check.name): $($check.detail)"
            if (-not [string]::IsNullOrWhiteSpace($check.fix)) {
                Write-Host "        Como corrigir: $($check.fix)" -ForegroundColor Yellow
            }
        }
        else {
            Write-Host "[AVISO] " -ForegroundColor Yellow -NoNewline
            Write-Host "$($check.name): $($check.detail)"
        }
    }

    if ($warnings.Count -gt 0) {
        Write-Host ""
        Write-Host "PORTAS EM USO" -ForegroundColor Yellow
        foreach ($warning in $warnings) {
            Write-Host "- $warning"
        }
        Write-Host "Portas ocupadas são normais se os serviços da Orkestral já estiverem em execução."
    }

    Write-Host ""
    if ($allRequiredOk) {
        Write-Host "AMBIENTE COMPLETO: todos os requisitos estão disponíveis." -ForegroundColor Green
    }
    else {
        Write-Host "AMBIENTE INCOMPLETO: $($requiredFailures.Count) requisito(s) precisam de atenção." -ForegroundColor Red
    }
}

if ($allRequiredOk) { exit 0 } else { exit 1 }
