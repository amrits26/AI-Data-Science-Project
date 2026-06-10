$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Users\amrit\OneDrive\Documents\AI Data Science Project"
$SqliteUrl = "sqlite:///./data/imperial_cars.db"
$VehicleCsv = ".\data\vehicle_data_sample.csv"
$OutLog = ".\data\backend.out.log"
$ErrLog = ".\data\backend.err.log"
$WikipediaWorkers = 12

Set-Location $ProjectRoot

if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
    throw "Virtual environment not found at .\.venv"
}

. .\.venv\Scripts\Activate.ps1

Write-Host "[1/8] Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Write-Host "[2/8] Checking DATABASE_URL and deciding PostgreSQL vs SQLite..."
$dbCheckCode = @'
import json
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
db_url = os.getenv("DATABASE_URL", "")
result = {"database_url": db_url, "postgres_ok": False, "error": None}
if db_url.startswith("postgresql"):
    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        result["postgres_ok"] = True
    except Exception as exc:
        result["error"] = str(exc)
print(json.dumps(result))
'@
$dbResult = .\.venv\Scripts\python.exe -c $dbCheckCode | ConvertFrom-Json

if (-not $dbResult.postgres_ok) {
    Write-Host "PostgreSQL unavailable. Falling back to SQLite: $SqliteUrl" -ForegroundColor Yellow
    $env:DATABASE_URL = $SqliteUrl

    if (Test-Path .env) {
        $envText = Get-Content .env -Raw
        if ($envText -match '(?m)^\s*DATABASE_URL\s*=') {
            $envText = [regex]::Replace($envText, '(?m)^\s*DATABASE_URL\s*=.*$', "DATABASE_URL=$SqliteUrl")
        }
        else {
            $envText = $envText + "`r`nDATABASE_URL=$SqliteUrl`r`n"
        }
        Set-Content .env $envText -Encoding utf8
    }
    else {
        "DATABASE_URL=$SqliteUrl" | Out-File .env -Encoding utf8
    }
}
else {
    Write-Host "PostgreSQL connection is healthy. Keeping existing DATABASE_URL." -ForegroundColor Green
    $env:DATABASE_URL = [string]$dbResult.database_url
}

Write-Host "[3/8] Initializing DB schema and ensuring cars table exists..."
$countCode = @'
from backend.app.database.db import init_db, get_db_session
from backend.app.database.models import Car

init_db()
db = get_db_session()
try:
    print(db.query(Car).count())
finally:
    db.close()
'@
$carCount = [int](.\.venv\Scripts\python.exe -c $countCode | Select-Object -Last 1)
Write-Host "Cars currently in DB: $carCount"

if ($carCount -eq 0) {
    Write-Host "[4/8] Inventory empty. Running scraper..." -ForegroundColor Yellow
    .\.venv\Scripts\python.exe scripts\inventory_scraper.py
    $carCount = [int](.\.venv\Scripts\python.exe -c $countCode | Select-Object -Last 1)

    if ($carCount -eq 0 -and (Test-Path .\data\inventory_backup.csv)) {
        Write-Host "Scraper returned zero rows. Importing fallback data/inventory_backup.csv..." -ForegroundColor Yellow
        $importCode = @'
import pandas as pd
from datetime import datetime
from backend.app.database.db import init_db, get_db_session
from backend.app.database.models import Car

init_db()
df = pd.read_csv('data/inventory_backup.csv', low_memory=False)

def to_int(v):
    try:
        if pd.isna(v):
            return None
        return int(float(str(v).replace(',', '').replace('$', '')))
    except Exception:
        return None

def to_float(v):
    try:
        if pd.isna(v):
            return None
        return float(str(v).replace(',', '').replace('$', ''))
    except Exception:
        return None

now = datetime.utcnow()
db = get_db_session()
try:
    existing = {
        (str(c.vin or '').strip().upper(), str(c.stock_number or '').strip().upper(), str(c.detail_url or '').strip()): c
        for c in db.query(Car).all()
    }
    inserted = 0
    updated = 0
    for _, row in df.iterrows():
        vin = str(row.get('vin') or '').strip().upper()
        stock = str(row.get('stock_number') or '').strip().upper()
        detail = str(row.get('source_url') or row.get('detail_url') or '').strip()
        key = (vin, stock, detail)
        car = existing.get(key)

        year = to_int(row.get('year'))
        make = str(row.get('make') or '').strip()
        model = str(row.get('model') or '').strip()
        if not year or not make or not model:
            continue

        if car is None:
            car = Car(year=year, make=make, model=model)
            inserted += 1
        else:
            updated += 1

        car.trim = str(row.get('trim') or car.trim or '').strip() or None
        car.vin = vin[:32] or None
        car.stock_number = stock[:64] or None
        car.detail_url = detail[:500] or None
        car.color = str(row.get('color') or car.color or '').strip()[:50] or None
        mileage = to_int(row.get('mileage'))
        if mileage is not None:
            car.mileage = mileage
        price = to_float(row.get('price'))
        msrp = to_float(row.get('msrp'))
        if price is not None:
            car.used_avg_price = price
            if car.msrp is None:
                car.msrp = price
        if msrp is not None:
            car.msrp = msrp
        car.available = True
        car.availability_status = 'available'
        car.last_seen = now
        car.last_updated = now
        db.add(car)

    db.commit()
    print({'inserted': inserted, 'updated': updated, 'total': db.query(Car).count()})
finally:
    db.close()
'@
        .\.venv\Scripts\python.exe -c $importCode
        $carCount = [int](.\.venv\Scripts\python.exe -c $countCode | Select-Object -Last 1)
    }
}

if ($carCount -eq 0) {
    throw "Cars table is still empty after scraper and fallback import."
}

Write-Host "Inventory ready with $carCount cars." -ForegroundColor Green

Write-Host "[5/8] Running spec enrichment..."
if (-not (Test-Path $VehicleCsv)) {
    Invoke-WebRequest -Uri "https://raw.githubusercontent.com/vbalagovic/cars-dataset/main/vehicle_data_sample.csv" -OutFile $VehicleCsv
}
$enrichResult = .\.venv\Scripts\python.exe scripts\enrich_specs.py --csv $VehicleCsv
Write-Host $enrichResult

Write-Host "[6/8] Building encyclopedia..."
.\.venv\Scripts\python.exe scripts\build_encyclopedia.py --limit-models 1 --limit-vehicles 1 --wikipedia-workers $WikipediaWorkers

if (-not (Test-Path .\data\automotive_encyclopedia.txt)) {
    throw "Expected data/automotive_encyclopedia.txt was not created."
}
$encyclopediaSize = (Get-Item .\data\automotive_encyclopedia.txt).Length
Write-Host "Encyclopedia size: $encyclopediaSize bytes"

Write-Host "[7/8] Ingesting encyclopedia into FAISS..."
.\.venv\Scripts\python.exe scripts\ingest_documents.py .\data\automotive_encyclopedia.txt

$meta = Get-Content .\knowledge_base\metadata.json -Raw | ConvertFrom-Json
if ([int]$meta.chunks -le 0) {
    throw "FAISS metadata indicates zero chunks."
}

Write-Host "[8/8] Restarting backend and running smoke tests..."
$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*uvicorn*backend.app.main:app*" }
foreach ($p in $procs) {
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

if (Test-Path $OutLog) { Remove-Item $OutLog -Force }
if (Test-Path $ErrLog) { Remove-Item $ErrLog -Force }

$backendProc = Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000" -WorkingDirectory $ProjectRoot -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -PassThru

Start-Sleep -Seconds 6

$health = $null
for ($attempt = 1; $attempt -le 15; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -Method Get -TimeoutSec 8
        break
    }
    catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $health) {
    if (Test-Path $OutLog) { Get-Content $OutLog -Tail 120 }
    if (Test-Path $ErrLog) { Get-Content $ErrLog -Tail 120 }
    throw "Backend health check failed after restart."
}

$smokeBody = @{ question = "What is AWD?" } | ConvertTo-Json
$smoke = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/ask" -Method Post -ContentType "application/json" -Body $smokeBody -TimeoutSec 30

$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254*" -and $_.PrefixOrigin -ne "WellKnown" } | Select-Object -First 1 -ExpandProperty IPAddress)
if (-not $ip) { $ip = "YOUR_LAPTOP_IP" }

Write-Host ""
Write-Host "Car Guru deployment summary" -ForegroundColor Green
Write-Host "DATABASE_URL: $env:DATABASE_URL"
Write-Host "Cars in DB: $carCount"
Write-Host "Encyclopedia bytes: $encyclopediaSize"
Write-Host "FAISS chunks: $($meta.chunks)"
Write-Host "Health: $($health.status)"
Write-Host "Ask source: $($smoke.source)"
Write-Host "Ask type: $($smoke.question_type)"
Write-Host "Ask answer preview: $($smoke.answer.Substring(0, [Math]::Min($smoke.answer.Length, 220)))"
Write-Host ""
Write-Host "Access URLs:"
Write-Host "http://127.0.0.1:8000"
Write-Host "http://$ip`:8000"