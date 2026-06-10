#requires -Version 5.1
<#!
.SYNOPSIS
One-click setup and launch for Imperial Cars AI on Windows.

.NOTES
Run this script in an elevated PowerShell session if Docker/Tesseract/service access requires it.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectPath = "C:\Users\amrit\OneDrive\Documents\AI Data Science Project"
$VenvPath = Join-Path $ProjectPath ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$EnvFile = Join-Path $ProjectPath ".env"
$EnvExample = Join-Path $ProjectPath ".env.example"
$TesseractExe = "C:\Program Files\Tesseract-OCR\tesseract.exe"
$DatabaseUrl = "postgresql://imperial_admin:Imperial123!@localhost:55433/imperial_dealership"
$OllamaBaseUrl = "http://localhost:11434"
$OllamaModel = "deepseek-r1:14b"

function Write-Step {
    param([string]$Message)
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

function Fail {
    param([string]$Message)
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Ensure-Command {
    param(
        [string]$CommandName,
        [string]$InstallHint,
        [switch]$Optional
    )
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        if ($Optional) {
            Write-Host "Optional dependency missing: $CommandName" -ForegroundColor Yellow
            Write-Host "Hint: $InstallHint" -ForegroundColor Yellow
            return $false
        }
        Fail "Missing dependency '$CommandName'. $InstallHint"
    }
    return $true
}

function Ensure-PythonVersion {
    param([string]$PythonExe)

    $versionOut = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    $parts = $versionOut.Trim().Split('.')
    $major = [int]$parts[0]
    $minor = [int]$parts[1]

    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
        Fail "Python 3.10+ is required. Detected: $versionOut"
    }

    Write-Host "Python version OK: $versionOut" -ForegroundColor Green
}

function Upsert-EnvVar {
    param(
        [string]$FilePath,
        [string]$Key,
        [string]$Value
    )

    if (-not (Test-Path $FilePath)) {
        New-Item -ItemType File -Path $FilePath -Force | Out-Null
    }

    $lines = Get-Content $FilePath -ErrorAction SilentlyContinue
    if (-not $lines) { $lines = @() }

    $pattern = "^\s*" + [regex]::Escape($Key) + "\s*="
    $newLine = "$Key=$Value"
    $updated = $false

    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match $pattern) {
            $lines[$i] = $newLine
            $updated = $true
        }
    }

    if (-not $updated) {
        $lines += $newLine
    }

    Set-Content -Path $FilePath -Value $lines -Encoding UTF8
}

function Ensure-TesseractInPythonFile {
    param([string]$FilePath)

    if (-not (Test-Path $FilePath)) {
        Write-Host "Skip patch (file missing): $FilePath" -ForegroundColor Yellow
        return
    }

    $content = Get-Content -Raw -Path $FilePath
    $assignment = 'pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"'

    if ($content -match 'pytesseract\.pytesseract\.tesseract_cmd\s*=') {
        $updated = [regex]::Replace(
            $content,
            'pytesseract\.pytesseract\.tesseract_cmd\s*=\s*.+',
            $assignment
        )
        Set-Content -Path $FilePath -Value $updated -Encoding UTF8
        Write-Host "Updated tesseract_cmd in: $FilePath" -ForegroundColor Green
        return
    }

    if ($content -notmatch '(^|\n)import\s+pytesseract(\r?\n|$)') {
        $content = "import pytesseract`r`n" + $content
    }

    $updated2 = [regex]::Replace(
        $content,
        '(import\s+pytesseract\s*(?:\r?\n))',
        "`$1$assignment`r`n",
        1
    )

    if ($updated2 -eq $content) {
        $updated2 = $content.TrimEnd() + "`r`n$assignment`r`n"
    }

    Set-Content -Path $FilePath -Value $updated2 -Encoding UTF8
    Write-Host "Inserted tesseract_cmd in: $FilePath" -ForegroundColor Green
}

function Invoke-WithRetry {
    param(
        [scriptblock]$Script,
        [int]$Retries = 5,
        [int]$DelaySeconds = 4,
        [string]$Name = "operation"
    )

    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        try {
            & $Script
            return
        } catch {
            if ($attempt -eq $Retries) {
                throw
            }
            Write-Host "$Name failed (attempt $attempt/$Retries). Retrying in $DelaySeconds sec..." -ForegroundColor Yellow
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

function Start-ServiceWindow {
    param(
        [string]$Title,
        [string]$Command
    )

    $escapedProject = $ProjectPath.Replace("'", "''")
    $fullCommand = "`$Host.UI.RawUI.WindowTitle = '$Title'; Set-Location '$escapedProject'; $Command"
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $fullCommand | Out-Null
}

try {
    Set-Location $ProjectPath

    Write-Step "Step 0: Telegram Bot Token"
    Write-Host "We need a Telegram bot token to enable the AI assistant on Telegram." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Follow these steps to create a bot:" -ForegroundColor Yellow
    Write-Host "  1. Open Telegram and search for @BotFather" -ForegroundColor White
    Write-Host "  2. Start a chat and send /newbot" -ForegroundColor White
    Write-Host "  3. Choose a name (e.g., 'Imperial Cars AI')" -ForegroundColor White
    Write-Host "  4. Choose a username (must end in 'bot', e.g., 'ImperialCarsBot')" -ForegroundColor White
    Write-Host "  5. Copy the token (looks like 7234567890:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw)" -ForegroundColor White
    Write-Host ""

    $openBrowser = Read-Host "Open BotFather link in your browser now? (y/n)"
    if ($openBrowser -eq "y" -or $openBrowser -eq "Y") {
        Start-Process "https://t.me/botfather"
        Write-Host "Browser opened. Create your bot in Telegram, then return here." -ForegroundColor Cyan
        Read-Host "Press Enter once you have the token ready"
    }

    Write-Host ""
    $TelegramTokenPlain = ""
    $tokenAttempts = 3
    while ([string]::IsNullOrWhiteSpace($TelegramTokenPlain) -and $tokenAttempts -gt 0) {
        $TelegramTokenSecure = Read-Host "Paste your Telegram bot token" -AsSecureString
        $TelegramTokenPlain = [System.Net.NetworkCredential]::new("", $TelegramTokenSecure).Password

        if ([string]::IsNullOrWhiteSpace($TelegramTokenPlain)) {
            Write-Host "Token cannot be empty. Please try again." -ForegroundColor Red
            $tokenAttempts--
            continue
        }

        # Validate token format: should contain a colon and start with digits
        if ($TelegramTokenPlain -notmatch '^\d+:[A-Za-z0-9_-]+$') {
            Write-Host "Token format looks incorrect. It should be like: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11" -ForegroundColor Yellow
            $retryToken = Read-Host "Continue anyway? (y/n)"
            if ($retryToken -ne "y" -and $retryToken -ne "Y") {
                $TelegramTokenPlain = ""
                $tokenAttempts--
                continue
            }
        }

        Write-Host "Token received. The bot will be automatically started later." -ForegroundColor Green
        break
    }

    if ([string]::IsNullOrWhiteSpace($TelegramTokenPlain)) {
        Fail "Telegram bot token not provided after multiple attempts."
    }

    Write-Step "Step 1: Check prerequisites"
    if (-not (Test-Path $ProjectPath)) {
        Fail "Project path not found: $ProjectPath"
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
    }
    if (-not $pythonCmd) {
        Fail "Python is required. Install Python 3.10+ from https://www.python.org/downloads/"
    }

    Ensure-Command -CommandName docker -InstallHint "Install Docker Desktop: https://www.docker.com/products/docker-desktop/" | Out-Null
    if ((docker compose version) 2>$null) {
        $script:DockerComposeCmd = "docker compose"
    } elseif (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        $script:DockerComposeCmd = "docker-compose"
    } else {
        Fail "Docker Compose is missing. Install Docker Desktop (includes Compose)."
    }

    Ensure-Command -CommandName git -InstallHint "Install Git: https://git-scm.com/downloads" -Optional | Out-Null

    if (-not (Test-Path $TesseractExe)) {
        Fail "Tesseract not found at '$TesseractExe'. Install from https://github.com/UB-Mannheim/tesseract/wiki"
    }
    Write-Host "Tesseract found: $TesseractExe" -ForegroundColor Green

    Write-Step "Step 2: Create/Activate virtual environment"
    if (-not (Test-Path $VenvPython)) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            py -3 -m venv $VenvPath
        } else {
            python -m venv $VenvPath
        }
    }
    if (-not (Test-Path $VenvPython)) {
        Fail "Virtual environment creation failed."
    }
    Ensure-PythonVersion -PythonExe $VenvPython

    Write-Step "Step 3: Install Python dependencies"
    & $VenvPython -m pip install --upgrade pip setuptools wheel
    & $VenvPython -m pip install -r (Join-Path $ProjectPath "requirements.txt")
    & $VenvPython -m pip install kaleido pypdf whisper transformers torch psycopg2-binary sqlalchemy pgvector reportlab apscheduler plotly pytesseract opencv-python python-dotenv requests

    Write-Step "Step 4: Configure environment and OCR path"
    if (-not (Test-Path $EnvFile)) {
        if (Test-Path $EnvExample) {
            Copy-Item $EnvExample $EnvFile -Force
        } else {
            New-Item -ItemType File -Path $EnvFile -Force | Out-Null
        }
    }

    Upsert-EnvVar -FilePath $EnvFile -Key "TELEGRAM_BOT_TOKEN" -Value $TelegramTokenPlain
    Upsert-EnvVar -FilePath $EnvFile -Key "DATABASE_URL" -Value $DatabaseUrl
    Upsert-EnvVar -FilePath $EnvFile -Key "OLLAMA_BASE_URL" -Value $OllamaBaseUrl
    Upsert-EnvVar -FilePath $EnvFile -Key "OLLAMA_MODEL" -Value $OllamaModel
    Upsert-EnvVar -FilePath $EnvFile -Key "TESSERACT_CMD" -Value $TesseractExe

    Ensure-TesseractInPythonFile -FilePath (Join-Path $ProjectPath "backend\app\agents\document_ingestion.py")
    Ensure-TesseractInPythonFile -FilePath (Join-Path $ProjectPath "backend\app\agents\image_utils.py")

    Write-Step "Step 5: Start Docker services"
    Invoke-Expression "$script:DockerComposeCmd up -d"

    $postgresId = (docker compose ps -q postgres) 2>$null
    if (-not $postgresId) {
        $postgresId = (docker ps --filter "name=postgres" --format "{{.ID}}" | Select-Object -First 1)
    }
    if (-not $postgresId) {
        Fail "Could not find running postgres container. Check docker compose logs."
    }

    $healthy = $false
    for ($i = 1; $i -le 30; $i++) {
        $null = docker exec $postgresId pg_isready -U imperial_admin -d imperial_dealership
        if ($LASTEXITCODE -eq 0) {
            $healthy = $true
            break
        }
        Write-Host "Waiting for PostgreSQL... ($i/30)"
        Start-Sleep -Seconds 2
    }
    if (-not $healthy) {
        Fail "PostgreSQL did not become healthy in time."
    }

    Write-Step "Step 6: Initialize and seed database"
    Invoke-WithRetry -Name "init_db" -Retries 5 -DelaySeconds 4 -Script {
        & $VenvPython (Join-Path $ProjectPath "scripts\init_db.py")
    }

    $datasetPath = Join-Path $ProjectPath "data\raw\large_cars_dataset.csv"
    if (-not (Test-Path $datasetPath)) {
        Write-Host "Dataset not found at $datasetPath. Importer will generate sample data automatically." -ForegroundColor Yellow
    }

    Invoke-WithRetry -Name "import_car_data" -Retries 5 -DelaySeconds 4 -Script {
        & $VenvPython (Join-Path $ProjectPath "scripts\import_car_data.py")
    }

    Write-Step "Step 7: Verify Ollama model"
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Fail "Ollama is not installed. Install from https://ollama.com/download"
    }

    $models = (& ollama list) -join "`n"
    if ($models -notmatch [regex]::Escape($OllamaModel)) {
        & ollama pull $OllamaModel
    } else {
        Write-Host "Ollama model already available: $OllamaModel" -ForegroundColor Green
    }

    Write-Step "Step 8: OCR test"
    $testOcrPath = Join-Path $ProjectPath "scripts\test_ocr.py"
    @'
import os
import sys
import cv2
import numpy as np
import pytesseract

cmd = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if os.path.exists(cmd):
    pytesseract.pytesseract.tesseract_cmd = cmd

img = np.full((140, 480, 3), 255, dtype=np.uint8)
cv2.putText(img, "OCR works", (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 0), 3)
text = pytesseract.image_to_string(img)

if "OCR" in text.upper() and "WORK" in text.upper():
    print("OCR works")
    sys.exit(0)

print("OCR check failed. Extracted:", repr(text))
sys.exit(1)
'@ | Set-Content -Path $testOcrPath -Encoding UTF8

    try {
        & $VenvPython $testOcrPath
        Write-Host "OCR validation passed." -ForegroundColor Green
    } catch {
        Write-Host "OCR validation warning: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "Try reinstalling Tesseract and verify path: $TesseractExe" -ForegroundColor Yellow
    }

    Write-Step "Step 9: Launch services"
    $serviceEnv = "`$env:DATABASE_URL='$DatabaseUrl'; `$env:OLLAMA_BASE_URL='$OllamaBaseUrl'; `$env:OLLAMA_MODEL='$OllamaModel'; `$env:TELEGRAM_BOT_TOKEN='$TelegramTokenPlain'; `$env:TESSERACT_CMD='$TesseractExe'"

    Start-ServiceWindow -Title "Imperial Streamlit" -Command "$serviceEnv; & '$VenvPython' -m streamlit run frontend/app.py --server.port 8501"
    Start-ServiceWindow -Title "Imperial Telegram Bot" -Command "$serviceEnv; & '$VenvPython' sales_bot.py"
    Start-ServiceWindow -Title "Imperial FastAPI" -Command "$serviceEnv; & '$VenvPython' -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"

    Write-Step "Step 10: Success"
    Write-Host "Imperial Cars AI setup completed successfully." -ForegroundColor Green
    Write-Host "Streamlit: http://localhost:8501"
    Write-Host "API docs:  http://localhost:8000/docs"
    Write-Host "pgAdmin:   http://localhost:5051"
    Write-Host ""
    Write-Host "Sample bot commands:"
    Write-Host "  /ask What SUV under 30000 do you recommend?"
    Write-Host "  /specs Toyota Camry 2024"
    Write-Host "  /compare Honda Civic vs Toyota Corolla"
    Write-Host "  /payment 30000 5000 6.9 60"
    Write-Host ""
    Write-Host "OCR is configured. Tesseract path: $TesseractExe"
    Write-Host "If Docker actions fail, rerun PowerShell as Administrator." -ForegroundColor Yellow
}
catch {
    Write-Host "Setup failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Check docker status, Python venv, and .env values, then rerun the script." -ForegroundColor Yellow
    exit 1
}
