param(
    [string]$ApiBaseUrl = $(if ($env:API_BASE_URL) { $env:API_BASE_URL } else { "http://localhost:8000" }),
    [string]$OllamaBaseUrl = $(if ($env:OLLAMA_BASE_URL) { $env:OLLAMA_BASE_URL } else { "http://localhost:11434" }),
    [string]$ModelName = $(if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { "imperial_deepseek" })
)

$ErrorActionPreference = "Stop"

Write-Host "=== Imperial Cars AI Health Check ==="
Write-Host "API base:    $ApiBaseUrl"
Write-Host "Ollama base: $OllamaBaseUrl"
Write-Host "Model:       $ModelName"
Write-Host ""

$failed = $false

# 1) API health
try {
    $healthUrl = "$($ApiBaseUrl.TrimEnd('/'))/api/health"
    $apiResp = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 12
    Write-Host "[OK] API health endpoint reachable: $healthUrl"
    $apiResp | ConvertTo-Json -Depth 8
}
catch {
    Write-Host "[FAIL] API health endpoint failed: $($_.Exception.Message)" -ForegroundColor Red
    $failed = $true
}

Write-Host ""

# 2) Ollama server check
try {
    $tagsUrl = "$($OllamaBaseUrl.TrimEnd('/'))/api/tags"
    $tagsResp = Invoke-RestMethod -Uri $tagsUrl -Method Get -TimeoutSec 10
    Write-Host "[OK] Ollama reachable: $tagsUrl"

    $allModels = @()
    if ($tagsResp.models) {
        $allModels = $tagsResp.models | ForEach-Object { $_.name }
    }

    if ($allModels.Count -gt 0) {
        Write-Host "Available models:"
        $allModels | ForEach-Object { Write-Host " - $_" }
    }
    else {
        Write-Host "No models returned by Ollama tags endpoint."
    }

    if ($allModels -contains $ModelName) {
        Write-Host "[OK] Target model found: $ModelName"
    }
    else {
        Write-Host "[WARN] Target model not found in tags: $ModelName" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "[FAIL] Ollama check failed: $($_.Exception.Message)" -ForegroundColor Red
    $failed = $true
}

Write-Host ""

# 3) Optional loaded model check
try {
    $psUrl = "$($OllamaBaseUrl.TrimEnd('/'))/api/ps"
    $psResp = Invoke-RestMethod -Uri $psUrl -Method Get -TimeoutSec 10

    $loaded = @()
    if ($psResp.models) {
        $loaded = $psResp.models | ForEach-Object { $_.name }
    }

    if ($loaded.Count -gt 0) {
        Write-Host "Loaded models:"
        $loaded | ForEach-Object { Write-Host " - $_" }
    }
    else {
        Write-Host "No currently loaded models (this can be normal before first request)."
    }

    if ($loaded -contains $ModelName) {
        Write-Host "[OK] Target model currently loaded: $ModelName"
    }
    else {
        Write-Host "[INFO] Target model not currently loaded: $ModelName" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "[WARN] Optional model process check failed: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
if ($failed) {
    Write-Host "Health check result: FAILED" -ForegroundColor Red
    exit 1
}

Write-Host "Health check result: PASSED" -ForegroundColor Green
exit 0
