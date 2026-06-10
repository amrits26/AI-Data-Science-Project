Param(
  [string]$ProjectRoot = "C:\Users\amrit\OneDrive\Documents\AI Data Science Project",
  [string]$PythonExe = "",
  [string]$BaseModel = "deepseek-ai/deepseek-r1-distill-qwen-1.5b"
)

$ErrorActionPreference = "Stop"

if (-not $PythonExe) {
  $PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
}

if (-not (Test-Path $PythonExe)) {
  throw "Python executable not found: $PythonExe"
}

Write-Output "[weekly] ProjectRoot=$ProjectRoot"
Write-Output "[weekly] PythonExe=$PythonExe"

Set-Location $ProjectRoot

# 1) Pull new chat logs / feedback (local files already accumulating).
Write-Output "[weekly] Using local data snapshots from data/*.csv"

# 2) Prepare fine-tune dataset.
& $PythonExe (Join-Path $ProjectRoot "scripts\prepare_finetune_data.py") --data_dir (Join-Path $ProjectRoot "data") --output (Join-Path $ProjectRoot "data\finetune_sales_data.jsonl")
if ($LASTEXITCODE -ne 0) { throw "prepare_finetune_data.py failed" }

# 3) Run LoRA fine-tune.
& $PythonExe (Join-Path $ProjectRoot "scripts\finetune_sales_style.py") --data_path (Join-Path $ProjectRoot "data\finetune_sales_data.jsonl") --output_dir (Join-Path $ProjectRoot "models\sales_finetuned") --base_model $BaseModel --epochs 1 --batch_size 4 --learning_rate 2e-4
if ($LASTEXITCODE -ne 0) { throw "finetune_sales_style.py failed" }

# 4) Optional evaluation pass.
& $PythonExe (Join-Path $ProjectRoot "scripts\evaluate_sales_model.py") --data_path (Join-Path $ProjectRoot "data\finetune_sales_data.jsonl") --base_model $BaseModel --adapter_path (Join-Path $ProjectRoot "models\sales_finetuned") --max_eval_samples 30 --output_path (Join-Path $ProjectRoot "data\sales_eval_comparisons.jsonl")
if ($LASTEXITCODE -ne 0) { Write-Warning "evaluate_sales_model.py failed; continuing restart" }

# 5) Restart backend.
$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
  Write-Output "[weekly] Stopping existing backend process $($conn.OwningProcess)"
  Stop-Process -Id $conn.OwningProcess -Force
}

Write-Output "[weekly] Starting backend"
Start-Process -FilePath (Join-Path $ProjectRoot ".venv\Scripts\uvicorn.exe") -ArgumentList "backend.app.main:app --host 0.0.0.0 --port 8000" -WorkingDirectory $ProjectRoot

Write-Output "[weekly] Sales retrain pipeline completed"
