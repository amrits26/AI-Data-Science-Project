# run_finetuning.ps1
# Fully automated DeepSeek fine-tuning workflow for Imperial Cars (Windows, CPU-only friendly).
#
# What this script does:
# 1) Sets project working directory.
# 2) Stops hanging Python processes.
# 3) Recreates .venv from scratch.
# 4) Installs CPU-only PyTorch + fine-tuning dependencies.
# 5) Ensures training data exists (with fallback generator if needed).
# 6) Launches fine-tuning in the foreground while logging to finetuning.log.
#
# Note: Run from an elevated or normal PowerShell as needed.

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Do not treat stderr from native tools (python/pip/tqdm) as terminating PowerShell errors.
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$ProjectRoot = "C:\Users\amrit\OneDrive\Documents\AI Data Science Project"
$ScriptsDir = Join-Path $ProjectRoot "scripts"
$PrepareScript = Join-Path $ScriptsDir "prepare_training_data.py"
$FinetuneScript = Join-Path $ScriptsDir "finetune_deepseek.py"
$DataTrainingDir = Join-Path $ProjectRoot "data\training"
$TrainingDataPath = Join-Path $DataTrainingDir "imperial_qa.jsonl"
$VenvDir = Join-Path $ProjectRoot ".venv"
$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$LogPath = Join-Path $ProjectRoot "finetuning.log"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Assert-ProjectPath {
    if (-not (Test-Path -LiteralPath $ProjectRoot)) {
        throw "Project root not found: $ProjectRoot"
    }
}

function Resolve-PythonCommand {
    # Return command spec hashtable with executable path and any prefix args.
    # This supports both direct python.exe and Windows py launcher.
    $pythonCmd = Get-Command python -CommandType Application -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        try {
            $versionText = & $pythonCmd.Source -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null
            if ($LASTEXITCODE -eq 0 -and $versionText) {
                $parts = $versionText.Trim().Split('.')
                $major = [int]$parts[0]
                $minor = [int]$parts[1]
                if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
                    return @{ Exe = $pythonCmd.Source; PrefixArgs = @() }
                }
            }
        } catch {
            # Fall through to py launcher.
        }
    }

    $pyCmd = Get-Command py -CommandType Application -ErrorAction SilentlyContinue
    if ($pyCmd) {
        foreach ($selector in @("-3.13", "-3.12", "-3.11", "-3.10", "-3")) {
            try {
                $versionText = & $pyCmd.Source $selector -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null
                if ($LASTEXITCODE -eq 0 -and $versionText) {
                    $parts = $versionText.Trim().Split('.')
                    $major = [int]$parts[0]
                    $minor = [int]$parts[1]
                    if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
                        return @{ Exe = $pyCmd.Source; PrefixArgs = @($selector) }
                    }
                }
            } catch {
                # Try next selector.
            }
        }
    }

    throw "Python 3.10+ not found. Install Python 3.10+ and ensure 'python' or 'py' is available."
}

function Invoke-Python {
    param(
        [hashtable]$PythonSpec,
        [string[]]$PythonArgs
    )

    $allArgs = @($PythonSpec.PrefixArgs + $PythonArgs)
    & $PythonSpec.Exe @allArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $($PythonSpec.Exe) $($allArgs -join ' ')"
    }
}

function Ensure-RequiredScripts {
    # Required script check with clear guidance.
    if (-not (Test-Path -LiteralPath $FinetuneScript)) {
        Write-Err "Missing required script: $FinetuneScript"
        Write-Err "Please re-run the main AI prompt to generate missing files first, then run this script again."
        throw "Cannot continue without finetune_deepseek.py"
    }

    if (-not (Test-Path -LiteralPath $PrepareScript)) {
        Write-Err "Missing script: $PrepareScript"
        Write-Err "Please re-run the main AI prompt to generate missing files first."
        Write-Warn "Creating a fallback prepare_training_data.py that generates 500 synthetic Q&A pairs."

        if (-not (Test-Path -LiteralPath $ScriptsDir)) {
            New-Item -ItemType Directory -Path $ScriptsDir -Force | Out-Null
        }

        $fallback = @'
#!/usr/bin/env python
"""Fallback training data generator: creates 500 synthetic dealership Q&A pairs."""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = PROJECT_ROOT / "data" / "training" / "imperial_qa.jsonl"

BASE = [
    ("How should we follow up with a new lead?", "Thank them, confirm vehicle interest, and offer two test-drive windows."),
    ("What financing guidance should we give?", "Share estimated monthly ranges and invite pre-qualification."),
    ("How do we handle trade-ins?", "Collect VIN, mileage, condition, then provide a transparent appraisal process."),
    ("How should service reminders be written?", "Be friendly, include due service, and provide two booking options."),
]

rows = []
for i in range(500):
    q, a = BASE[i % len(BASE)]
    rows.append(
        {
            "instruction": f"{q} (Case #{i + 1})",
            "response": a,
        }
    )

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT.open("w", encoding="utf-8") as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")

print(f"Generated {len(rows)} synthetic pairs at {OUTPUT}")
'@

        Set-Content -LiteralPath $PrepareScript -Value $fallback -Encoding UTF8
    }
}

function Stop-HangingPython {
    Write-Step "Stopping hanging Python processes (if any)"
    $procNames = @("python", "python3", "pythonw")
    foreach ($name in $procNames) {
        Get-Process -Name $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
}

function Recreate-Venv {
    param([hashtable]$PythonSpec)

    Write-Step "Removing existing virtual environment (if present)"
    if (Test-Path -LiteralPath $VenvDir) {
        # PowerShell recursive delete can hang on large Windows venv trees.
        # Use cmd rmdir first, then fallback to Remove-Item.
        & cmd.exe /c "rmdir /s /q \"\"$VenvDir\"\""
        if (Test-Path -LiteralPath $VenvDir) {
            Remove-Item -LiteralPath $VenvDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $VenvDir) {
            throw "Failed to remove existing virtual environment: $VenvDir. Close terminals using .venv and retry."
        }
    }

    Write-Step "Creating new virtual environment"
    Invoke-Python -PythonSpec $PythonSpec -PythonArgs @("-m", "venv", ".venv")

    if (-not (Test-Path -LiteralPath $ActivateScript)) {
        throw "Virtual environment activation script not found: $ActivateScript"
    }

    Write-Step "Activating virtual environment"
    . $ActivateScript

    if (-not (Test-Path -LiteralPath $VenvPython)) {
        throw "Virtual environment Python executable not found: $VenvPython"
    }
}

function Install-Dependencies {
    Write-Step "Upgrading pip"
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }

    Write-Step "Installing CPU-only PyTorch"
    & $VenvPython -m pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision torchaudio
    if ($LASTEXITCODE -ne 0) { throw "CPU-only PyTorch installation failed" }

    Write-Step "Installing fine-tuning dependencies"
    $coreDeps = @("transformers", "datasets", "accelerate", "peft", "trl")
    & $VenvPython -m pip install @coreDeps
    if ($LASTEXITCODE -ne 0) { throw "Core fine-tuning dependency installation failed" }

    # bitsandbytes/unsloth can be platform-sensitive on Windows+CPU.
    # Keep them optional and prevent dependency resolution from downgrading torch.
    & $VenvPython -m pip install bitsandbytes
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Optional package 'bitsandbytes' could not be installed in this environment. Continuing."
    }

    & $VenvPython -m pip install unsloth --no-deps
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Optional package 'unsloth' could not be installed without dependency changes. Continuing."
    }

    # Re-assert CPU torch stack in case any optional package touched constraints.
    & $VenvPython -m pip install --index-url https://download.pytorch.org/whl/cpu --upgrade --force-reinstall torch torchvision torchaudio
    if ($LASTEXITCODE -ne 0) { throw "Failed to re-assert CPU-only PyTorch compatibility" }
}

function Ensure-TrainingData {
    Write-Step "Generating training data"
    & $VenvPython $PrepareScript
    if ($LASTEXITCODE -ne 0) {
        throw "Training data generation failed. Check $PrepareScript"
    }

    if (-not (Test-Path -LiteralPath $TrainingDataPath)) {
        throw "Training data file was not created: $TrainingDataPath"
    }
}

function Start-Finetuning {
    Write-Step "Launching fine-tuning in foreground and logging to finetuning.log"

    if (Test-Path -LiteralPath $LogPath) {
        Remove-Item -LiteralPath $LogPath -Force
    }

    Write-Host "Fine-tuning has started." -ForegroundColor Green
    Write-Host "Monitor progress with: Get-Content finetuning.log -Wait" -ForegroundColor Green
    Write-Host "Press Ctrl+C to stop." -ForegroundColor Green

    # Keep process in foreground and stream all output to console + log.
    # Use cmd.exe wrapper to avoid PowerShell classifying native stderr progress output as errors.
    $quotedPython = '"' + $VenvPython + '"'
    $quotedScript = '"' + $FinetuneScript + '"'
    & cmd.exe /c "$quotedPython $quotedScript" 2>&1 | Tee-Object -FilePath $LogPath -Append
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        throw "Fine-tuning process exited with code $exitCode"
    }

    Write-Host "`nFine-tuning completed successfully." -ForegroundColor Green
}

function Print-NextSteps {
    Write-Host "`nNext steps:" -ForegroundColor Cyan
    Write-Host "1) Test your fine-tuned model:" -ForegroundColor Cyan
    Write-Host "   .\.venv\Scripts\python.exe scripts\health_check.py" -ForegroundColor Gray
    Write-Host "2) Update .env to point to your fine-tuned model directory (example):" -ForegroundColor Cyan
    Write-Host "   MODEL_PATH=models/imperial_deepseek" -ForegroundColor Gray
    Write-Host "3) Restart your backend/service so it picks up new environment values." -ForegroundColor Cyan
}

try {
    Write-Step "Setting working directory"
    Assert-ProjectPath
    Set-Location -LiteralPath $ProjectRoot

    Ensure-RequiredScripts
    Stop-HangingPython

    $pythonSpec = Resolve-PythonCommand
    Recreate-Venv -PythonSpec $pythonSpec
    Install-Dependencies
    Ensure-TrainingData
    Start-Finetuning
    Print-NextSteps
}
catch {
    $message = $_.Exception.Message
    if (-not $message) {
        $message = $_.ToString()
    }
    Write-Err $message
    exit 1
}

# Intentionally do not close terminal. Script returns control only after completion or Ctrl+C.
