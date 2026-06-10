# setup_imperial_ollama_model.ps1
# Idempotent end-to-end setup for Imperial fine-tuned model in Ollama.

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Users\amrit\OneDrive\Documents\AI Data Science Project"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$AdapterDir = Join-Path $ProjectRoot "models\imperial_deepseek"
$MergedDir = Join-Path $ProjectRoot "models\imperial_deepseek_merged"
$GgufOut = Join-Path $MergedDir "imperial_deepseek_merged.gguf"
$PrimaryModelfile = Join-Path $ProjectRoot "Modelfile"
$GgufModelfile = Join-Path $ProjectRoot "Modelfile.gguf"
$MergeScript = Join-Path $ProjectRoot "merge_and_export.py"
$EnvFile = Join-Path $ProjectRoot ".env"
$LlamaCppDir = Join-Path $ProjectRoot "tools\llama.cpp"
$ConvertScript = Join-Path $LlamaCppDir "convert_hf_to_gguf.py"
$ModelName = "imperial_deepseek"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-WarnMsg {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-ErrMsg {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Assert-PathExists {
    param([string]$PathToCheck, [string]$Description)
    if (-not (Test-Path -LiteralPath $PathToCheck)) {
        throw "$Description not found: $PathToCheck"
    }
}

function Invoke-Process {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [switch]$IgnoreExitCode
    )

    $argText = if ($Arguments) { $Arguments -join " " } else { "" }
    Write-Host "Running: $FilePath $argText" -ForegroundColor DarkGray
    & $FilePath @Arguments
    $code = $LASTEXITCODE

    if (-not $IgnoreExitCode -and $code -ne 0) {
        throw "Command failed ($code): $FilePath $argText"
    }

    return $code
}

function Ensure-PrimaryModelfile {
    Write-Step "Creating primary Modelfile"
    $content = @'
FROM deepseek-r1:7b
ADAPTER C:/Users/amrit/OneDrive/Documents/AI Data Science Project/models/imperial_deepseek
PARAMETER temperature 0.7
PARAMETER top_p 0.9
'@
    Set-Content -LiteralPath $PrimaryModelfile -Value $content -Encoding UTF8
    Write-Ok "Primary Modelfile written: $PrimaryModelfile"
}

function Ensure-MergeScript {
    Write-Step "Creating merge_and_export.py"

    $content = @'
#!/usr/bin/env python
"""Merge LoRA adapter into base model and export merged HF model."""

from pathlib import Path
import traceback

from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

PROJECT_ROOT = Path(r"C:\Users\amrit\OneDrive\Documents\AI Data Science Project")
BASE_MODEL = "deepseek-ai/deepseek-r1-distill-qwen-7b"
ADAPTER_DIR = PROJECT_ROOT / "models" / "imperial_deepseek"
OUTPUT_DIR = PROJECT_ROOT / "models" / "imperial_deepseek_merged"


def main() -> int:
    try:
        if not ADAPTER_DIR.exists():
            print(f"ERROR: Adapter directory not found: {ADAPTER_DIR}")
            return 1

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        print(f"Loading tokenizer: {BASE_MODEL}")
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

        print(f"Loading base model: {BASE_MODEL}")
        base = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True,
            device_map="cpu",
        )

        print(f"Loading adapter: {ADAPTER_DIR}")
        peft_model = PeftModel.from_pretrained(base, str(ADAPTER_DIR))

        print("Merging adapter into base model")
        merged = peft_model.merge_and_unload()

        print(f"Saving merged model to: {OUTPUT_DIR}")
        merged.save_pretrained(str(OUTPUT_DIR), safe_serialization=True)
        tokenizer.save_pretrained(str(OUTPUT_DIR))

        print("Merge and export complete")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
'@

    Set-Content -LiteralPath $MergeScript -Value $content -Encoding UTF8
    Write-Ok "Merge script written: $MergeScript"
}

function Ensure-LlamaCpp {
    Write-Step "Ensuring llama.cpp is available"

    if (-not (Test-Path -LiteralPath $ConvertScript)) {
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
            throw "git is required to fetch llama.cpp but was not found on PATH."
        }

        if (Test-Path -LiteralPath $LlamaCppDir) {
            Remove-Item -LiteralPath $LlamaCppDir -Recurse -Force
        }

        New-Item -ItemType Directory -Path (Split-Path $LlamaCppDir -Parent) -Force | Out-Null
        Invoke-Process -FilePath "git" -Arguments @("clone", "https://github.com/ggerganov/llama.cpp.git", $LlamaCppDir)
    }

    Assert-PathExists -PathToCheck $ConvertScript -Description "llama.cpp converter script"
    Write-Ok "llama.cpp converter ready"
}

function Convert-MergedToGguf {
    Write-Step "Converting merged HF model to GGUF"

    Assert-PathExists -PathToCheck $VenvPython -Description "Python executable"
    Assert-PathExists -PathToCheck $MergedDir -Description "Merged model directory"

    Invoke-Process -FilePath $VenvPython -Arguments @($ConvertScript, $MergedDir, "--outfile", $GgufOut, "--outtype", "q8_0")

    Assert-PathExists -PathToCheck $GgufOut -Description "GGUF output"
    Write-Ok "GGUF created: $GgufOut"
}

function Ensure-GgufModelfile {
    Write-Step "Creating GGUF Modelfile"

    $normalized = $GgufOut -replace "\\", "/"
    $content = @"
FROM $normalized
PARAMETER temperature 0.7
PARAMETER top_p 0.9
"@
    Set-Content -LiteralPath $GgufModelfile -Value $content -Encoding UTF8
    Write-Ok "GGUF Modelfile written: $GgufModelfile"
}

function Try-CreateOllamaModel {
    param([string]$ModelfilePath)

    Write-Step "Creating Ollama model from $ModelfilePath"
    $code = Invoke-Process -FilePath "ollama" -Arguments @("create", $ModelName, "-f", $ModelfilePath) -IgnoreExitCode

    if ($code -ne 0) {
        Write-WarnMsg "ollama create failed with exit code $code"
        return $false
    }

    Write-Ok "Ollama model created: $ModelName"
    return $true
}

function Test-OllamaModel {
    Write-Step "Testing Ollama model"
    Invoke-Process -FilePath "ollama" -Arguments @("run", $ModelName, "What's your best price on a Toyota Camry?")
    Write-Ok "Ollama model test completed"
}

function Update-EnvModel {
    Write-Step "Updating .env model setting"

    if (-not (Test-Path -LiteralPath $EnvFile)) {
        Set-Content -LiteralPath $EnvFile -Value "OLLAMA_MODEL=$ModelName" -Encoding UTF8
        Write-Ok "Created .env with OLLAMA_MODEL=$ModelName"
        return
    }

    $text = Get-Content -LiteralPath $EnvFile -Raw
    if ($text -match "(?m)^OLLAMA_MODEL=") {
        $updated = [regex]::Replace($text, "(?m)^OLLAMA_MODEL=.*$", "OLLAMA_MODEL=$ModelName")
        Set-Content -LiteralPath $EnvFile -Value $updated -Encoding UTF8
    } else {
        $suffix = if ($text.EndsWith("`n")) { "" } else { "`r`n" }
        Set-Content -LiteralPath $EnvFile -Value ($text + $suffix + "OLLAMA_MODEL=$ModelName`r`n") -Encoding UTF8
    }

    Write-Ok ".env updated to OLLAMA_MODEL=$ModelName"
}

try {
    Write-Step "Starting Imperial Ollama model setup"

    Assert-PathExists -PathToCheck $ProjectRoot -Description "Project root"
    Set-Location -LiteralPath $ProjectRoot

    Assert-PathExists -PathToCheck $AdapterDir -Description "Adapter directory"
    Assert-PathExists -PathToCheck $VenvPython -Description "Python virtual environment"

    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        throw "Ollama is not installed or not on PATH."
    }

    Ensure-PrimaryModelfile

    $created = Try-CreateOllamaModel -ModelfilePath $PrimaryModelfile

    if (-not $created) {
        Write-WarnMsg "Falling back to merge-and-export flow."

        Ensure-MergeScript
        Invoke-Process -FilePath $VenvPython -Arguments @($MergeScript)

        Ensure-LlamaCpp
        Convert-MergedToGguf
        Ensure-GgufModelfile

        $created = Try-CreateOllamaModel -ModelfilePath $GgufModelfile
        if (-not $created) {
            throw "Fallback ollama create also failed."
        }
    }

    Test-OllamaModel
    Update-EnvModel

    Write-Host "`nModel is ready. The bot will now use the fine-tuned version." -ForegroundColor Green
    exit 0
}
catch {
    $msg = $_.Exception.Message
    if (-not $msg) { $msg = $_.ToString() }
    Write-ErrMsg $msg
    exit 1
}
