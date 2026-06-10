param(
    [string]$ProjectRoot = "C:\Users\amrit\OneDrive\Documents\AI Data Science Project"
)

$ErrorActionPreference = "Stop"

Write-Host "=== Imperial Cars AI Frontend Build ==="
Write-Host "Project root: $ProjectRoot"

if (-not (Test-Path $ProjectRoot)) {
    throw "Project root not found: $ProjectRoot"
}

$frontendDir = Join-Path $ProjectRoot "frontend-react"
if (-not (Test-Path $frontendDir)) {
    throw "Frontend directory not found: $frontendDir"
}

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue

if (-not $nodeCmd) {
    throw "Node.js is not installed or not on PATH. Install Node.js 18+ and retry."
}
if (-not $npmCmd) {
    throw "npm is not installed or not on PATH. Reinstall Node.js and retry."
}

Write-Host "Node: $($nodeCmd.Source)"
Write-Host "npm:  $($npmCmd.Source)"

Push-Location $frontendDir
try {
    Write-Host "Using frontend directory: $frontendDir"

    $nodeModules = Join-Path $frontendDir "node_modules"
    if (-not (Test-Path $nodeModules)) {
        Write-Host "node_modules not found. Installing dependencies..."
        if (Test-Path (Join-Path $frontendDir "package-lock.json")) {
            npm ci
        }
        else {
            npm install
        }
    }
    else {
        Write-Host "Dependencies already present (node_modules exists)."
    }

    Write-Host "Building frontend..."
    npm run build

    $distDir = Join-Path $frontendDir "dist"
    if (-not (Test-Path $distDir)) {
        throw "Build finished but dist folder is missing: $distDir"
    }

    Write-Host "Build complete. Dist output: $distDir"
}
finally {
    Pop-Location
}
