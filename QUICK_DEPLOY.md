# QUICK DEPLOY - Imperial Cars AI

## Local Laptop (Windows PowerShell)

### 1) Backend env + dependencies
```powershell
cd "C:\Users\amrit\OneDrive\Documents\AI Data Science Project"
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2) Database init + migrations
```powershell
python scripts\init_db.py
python scripts\migrate_add_daily_goals.py
python scripts\migrate_phase5_salesperson_and_video.py
python scripts\migrate_add_sales_stage_events.py
```

### 3) Start backend API
```powershell
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

### 4) Frontend
```powershell
cd frontend-react
npm install
npm run build
npm run preview -- --host 0.0.0.0 --port 3000
```

### 5) Optional bot/services
```powershell
cd "C:\Users\amrit\OneDrive\Documents\AI Data Science Project"
python sales_bot.py
```

### 6) Health + smoke
```powershell
python scripts\health_check.py
python scripts\smoke_customer_journey.py
```

### 7) Sales Copilot data prep
```powershell
python run_scraper.py
python setup_knowledge_base.py
```

If `ADMIN_API_SECRET` is configured, include header `x-admin-secret` when calling:
- `POST /api/dealership/scrape-inventory`
- `POST /api/knowledge/ingest`

## One-command production bootstrap
```powershell
cd "C:\Users\amrit\OneDrive\Documents\AI Data Science Project"
.\setup_production.ps1 -ApiPort 8013
```

## Scheduler (weekly inventory import)
```powershell
.\setup_task_scheduler.ps1
```

## Docker-style local deployment
```powershell
docker-compose up --build -d
```

## VPS (high-level)
1. Clone repo and set `.env`.
2. Create Python venv and install requirements.
3. Run DB init/migrations.
4. Start backend with `uvicorn` or process manager (systemd/supervisor).
5. Build frontend and serve static output (Nginx or `vite preview`).
6. Run health + smoke checks.
