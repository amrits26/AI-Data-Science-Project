param(
    [string]$ProjectRoot = (Resolve-Path ".").Path,
    [string]$PythonPath = ".\.venv\Scripts\python.exe",
    [int]$ApiPort = 8000,
    [switch]$SkipInstall,
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = "Stop"

Write-Host "== Imperial Cars Production Setup =="

function Test-PythonModule {
    param(
        [string]$PythonExe,
        [string]$ModuleName
    )
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $PythonExe -c "import $ModuleName" 1>$null 2>$null
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    return $LASTEXITCODE -eq 0
}

$resolvedProjectRoot = (Resolve-Path $ProjectRoot).Path
$resolvedPythonPath = if ([System.IO.Path]::IsPathRooted($PythonPath)) {
    $PythonPath
} else {
    Join-Path $resolvedProjectRoot $PythonPath
}

if (-not (Test-Path $resolvedPythonPath)) {
    throw "Python executable not found: $resolvedPythonPath"
}

Push-Location $resolvedProjectRoot
try {
    if (-not $SkipInstall) {
        Write-Host "[1/5] Installing backend dependencies"
        & $resolvedPythonPath -m pip install -r requirements.txt
    }
    else {
        Write-Host "[1/5] Skipping full dependency install"
    }

    if (-not (Test-PythonModule -PythonExe $resolvedPythonPath -ModuleName "uvicorn")) {
        Write-Host "Bootstrapping essential runtime modules (uvicorn missing)"
        & $resolvedPythonPath -m pip install fastapi "uvicorn[standard]" sqlalchemy requests python-dotenv reportlab
    }

    Write-Host "[2/5] Initializing database and Phase 5 migration"
    & $resolvedPythonPath scripts/init_db.py
    & $resolvedPythonPath scripts/migrate_phase5_salesperson_and_video.py

    if (-not $SkipFrontendBuild) {
        Write-Host "[3/5] Installing and building frontend"
        Push-Location "frontend-react"
        try {
            npm install
            npm run build
        }
        finally {
            Pop-Location
        }
    }

    Write-Host "[4/5] Starting backend API"
    $uvicornArgs = @("-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "$ApiPort")
    $process = Start-Process -FilePath $resolvedPythonPath -ArgumentList $uvicornArgs -WorkingDirectory $resolvedProjectRoot -PassThru
    Write-Host "Backend started with PID $($process.Id)"

    Write-Host "[5/5] Verifying health endpoint"
    $healthUrl = "http://localhost:$ApiPort/api/health"
    $healthy = $false
    for ($i = 0; $i -lt 20; $i++) {
        try {
            $response = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 5
            if ($response.status -in @("ok", "degraded")) {
                $healthy = $true
                $response | ConvertTo-Json -Depth 6
                break
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }

    if (-not $healthy) {
        throw "Health check failed at $healthUrl"
    }

    Write-Host "Production setup complete."
    Write-Host "Stop backend with: Stop-Process -Id $($process.Id)"
}
finally {
    Pop-Location
}
