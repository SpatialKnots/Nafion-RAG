param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TmpDir = Join-Path $ProjectRoot "tmp"
$HealthUrl = "http://${HostAddress}:${Port}/health"
$UiUrl = "http://${HostAddress}:${Port}/ui/"

function Write-Step {
    param([string]$Message)
    Write-Host "[ARIADNE] $Message"
}

function Resolve-AriadnePython {
    $candidates = @(
        (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
        (Join-Path $ProjectRoot ".venv312\Scripts\python.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    throw "Python was not found. Install Python 3.11+ or create a virtual environment in $ProjectRoot\.venv."
}

function Test-AriadneHealth {
    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

function Start-AriadneProcess {
    param(
        [string]$Name,
        [string]$Command,
        [string]$LogName
    )

    $stdout = Join-Path $TmpDir "$LogName.out.log"
    $stderr = Join-Path $TmpDir "$LogName.err.log"
    $quotedRoot = $ProjectRoot.Replace("'", "''")
    $fullCommand = "Set-Location -LiteralPath '$quotedRoot'; `$env:PYTHONPATH='$quotedRoot'; $Command"

    Write-Step "Starting $Name"
    Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $fullCommand) `
        -WindowStyle Minimized `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr | Out-Null
}

Set-Location -LiteralPath $ProjectRoot
New-Item -ItemType Directory -Force -Path $TmpDir | Out-Null

$Python = Resolve-AriadnePython
Write-Step "Project: $ProjectRoot"
Write-Step "Python: $Python"

if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".env")) -and (Test-Path -LiteralPath (Join-Path $ProjectRoot ".env.example"))) {
    Write-Step "Creating .env from .env.example"
    Copy-Item -LiteralPath (Join-Path $ProjectRoot ".env.example") -Destination (Join-Path $ProjectRoot ".env")
}

if (Test-AriadneHealth) {
    Write-Step "ARIADNE is already running at $UiUrl"
}
else {
    Write-Step "Applying database migrations"
    & $Python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Database migration failed. Check PostgreSQL and .env, then run this launcher again."
    }

    Start-AriadneProcess `
        -Name "API and UI" `
        -Command "& '$Python' -m uvicorn app.main:app --host $HostAddress --port $Port" `
        -LogName "ariadne-launcher-api"

    Start-Sleep -Seconds 3

    Start-AriadneProcess `
        -Name "background worker" `
        -Command "& '$Python' -m app.workers.worker" `
        -LogName "ariadne-launcher-worker"

    for ($attempt = 1; $attempt -le 20; $attempt++) {
        if (Test-AriadneHealth) {
            Write-Step "ARIADNE is ready at $UiUrl"
            break
        }
        Start-Sleep -Seconds 1
    }

    if (-not (Test-AriadneHealth)) {
        Write-Step "Server did not answer yet. Logs:"
        Write-Step (Join-Path $TmpDir "ariadne-launcher-api.err.log")
        Write-Step (Join-Path $TmpDir "ariadne-launcher-api.out.log")
    }
}

if (-not $NoBrowser) {
    Write-Step "Opening browser"
    Start-Process $UiUrl | Out-Null
}

Write-Step "Done. You can close this launcher window."
