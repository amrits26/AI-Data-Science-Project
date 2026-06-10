# train_sales_model.ps1
# One-click fine-tuning of the Imperial Cars AI on your real sales data

$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Users\amrit\OneDrive\Documents\AI Data Science Project"

Set-Location $ProjectRoot

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

Write-Host "=== Step 1: Preparing training data from deals, leads, feedback, and chat history ===" -ForegroundColor Cyan
python scripts/prepare_finetune_data.py --data_dir .\data --output .\data\finetune_sales_data.jsonl

if ($LASTEXITCODE -ne 0) {
    Write-Host "Data preparation failed. Check your CSV files." -ForegroundColor Red
    exit 1
}

# Optional: Check if we have enough samples
$samples = (Get-Content .\data\finetune_sales_data.jsonl | Measure-Object -Line).Lines
Write-Host "Prepared $samples training pairs." -ForegroundColor Green

if ($samples -lt 20) {
    Write-Host "WARNING: Very few samples. Consider adding more data before fine-tuning." -ForegroundColor Yellow
}

# Ask user if they want to use the larger 7B model (slower but better)
$use7B = Read-Host "Use 7B model? (y/n, default n)"
if ($use7B -eq 'y') {
    $baseModel = "deepseek-ai/deepseek-r1-distill-qwen-7b"
    $maxSamples = 1000  # keep lower for time
} else {
    $baseModel = "deepseek-ai/deepseek-r1-distill-qwen-1.5b"
    $maxSamples = 2000
}

Write-Host "=== Step 2: Fine-tuning sales style with LoRA (this will take hours) ===" -ForegroundColor Cyan
python scripts/finetune_sales_style.py `
    --data_path .\data\finetune_sales_data.jsonl `
    --output_dir .\models\sales_finetuned `
    --base_model $baseModel `
    --max_samples $maxSamples `
    --epochs 2 `
    --batch_size 4 `
    --learning_rate 2e-4

if ($LASTEXITCODE -ne 0) {
    Write-Host "Fine-tuning failed. Check error messages." -ForegroundColor Red
    exit 1
}

Write-Host "=== Step 3: Updating environment to enable fine-tuned model ===" -ForegroundColor Cyan
# Ensure .env has USE_SALES_FINETUNE=true and points to the correct path
$envFile = ".\.env"
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile
    if ($envContent -notmatch "USE_SALES_FINETUNE") {
        Add-Content $envFile "`nUSE_SALES_FINETUNE=true"
        Add-Content $envFile "SALES_MODEL_PATH=./models/sales_finetuned"
    } else {
        # Replace existing lines
        $envContent = $envContent -replace "USE_SALES_FINETUNE=.*", "USE_SALES_FINETUNE=true"
        $envContent = $envContent -replace "SALES_MODEL_PATH=.*", "SALES_MODEL_PATH=./models/sales_finetuned"
        Set-Content $envFile $envContent
    }
} else {
    Write-Host "No .env file found; create one with USE_SALES_FINETUNE=true" -ForegroundColor Yellow
}

Write-Host "=== Step 4: Restarting backend ===" -ForegroundColor Cyan
# Kill any existing uvicorn process on port 8000
$process = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($process) {
    Stop-Process -Id $process.OwningProcess -Force
    Write-Host "Stopped old backend process."
}

# Start backend in background (or foreground, but script will exit)
Write-Host "Starting new backend (keep this terminal open)..."
Start-Process -NoNewWindow -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"

Write-Host "=== Training complete! ===" -ForegroundColor Green
Write-Host "The fine-tuned sales model is now active." -ForegroundColor Green
Write-Host "Test on your tablet at http://10.20.0.91:8000" -ForegroundColor Cyan