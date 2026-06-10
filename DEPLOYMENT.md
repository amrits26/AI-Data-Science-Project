# Deployment Guide

## Docker Production Stack
The production compose file includes:
- `postgres`
- `ollama`
- `backend`
- `frontend`
- `nginx`

### Start
```powershell
docker compose -f docker-compose.prod.yml up -d --build
```

### Health check
```powershell
curl http://localhost/api/health
```

Nginx routes:
- `/api/*` -> backend
- `/` -> React frontend

## Railway
1. Connect repository in Railway.
2. Ensure `railway.json` is detected.
3. Set environment variables from `.env.example`.
4. Deploy.

Required Railway variables:
- `DATABASE_URL`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`
- `SMTP_*`

## Fly.io
1. Install flyctl and login.
2. Create app:
```bash
fly launch --name imperial-cars-ai
```
3. Set secrets and deploy:
```bash
fly secrets set DATABASE_URL=... OLLAMA_BASE_URL=... OLLAMA_MODEL=deepseek-r1:14b
fly deploy
```

## Bare Metal / VM
1. Run backend with gunicorn:
```bash
gunicorn --workers 3 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 backend.app.main:app
```
2. Build React:
```bash
cd frontend-react && npm install && npm run build
```
3. Serve React with nginx and proxy `/api` to backend.

## Post-Deploy Checklist
- `GET /api/health` returns `ok` or `degraded` with expected services.
- Follow-up flow sends on enabled customer channels only.
- OCR ingestion endpoint accepts image uploads.
- React tabs load without API contract errors.

## Phase Runbook Coverage (0-5)

### Phase 0 - Accessibility and Content Foundation
- Verify baseline UI rendering and accessibility checks pass.
- Run: `python -m pytest tests/test_accessibility.py -q`

### Phase 1 - Dual Mode UI
- Verify mode switching and app shell behavior in React.
- Run: `cd frontend-react; npm run type-check`

### Phase 2 - Psychology Sales Tools
- Verify financial calculators and sales APIs.
- Run: `python -m pytest tests/test_phase2_api.py -q`

### Phase 3 - Verde Sales Automation
- Verify lead logging, goals, and activity dashboard endpoints/UI.
- Run: `python -m pytest tests/test_phase3_api.py -q`

### Phase 4 - Trust and Relationship Features
- Verify trust badge, role/tone/conflict pathways.
- Run: `python -m pytest tests/test_phase4_api.py -q`

### Phase 5 - Portfolio and Content
- Verify dashboard KPIs, service videos, maintenance PDF, and voice UI fallback.
- Run: `python -m pytest tests/test_phase5_api.py -q`
- Run: `cd frontend-react; npm run test -- src/pages/ChatbotPhase5.test.tsx`

## Phase 6 Integration and Deployment

### 1) Configure environment
- Copy `.env.example` to `.env` and set runtime values.

### 2) Production bootstrap script
- Run from project root:
```powershell
.\setup_production.ps1
```

This script performs install/init/build/start/health flow:
- installs backend dependencies
- initializes DB and runs Phase 5 migration
- installs/builds frontend
- starts backend server
- validates `GET /api/health`

### 3) Weekly inventory scheduler
- Register scheduled task (Monday 02:00):
```powershell
.\setup_task_scheduler.ps1
```

### 4) Health and smoke validation
- Health endpoint:
```powershell
python scripts/health_check.py
```
- End-to-end customer journey smoke:
```powershell
python scripts/smoke_customer_journey.py
```

### 5) Observability expectations
- API requests are emitted as structured JSON-lines logs.
- Health endpoint includes checks for database, twilio, pdf generation, and inventory staleness.
