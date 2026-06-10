# Imperial Cars AI - Production Guide

Imperial Cars AI is a local-first dealership assistant with:
- FastAPI backend for AI chat, inventory, calculators, OCR ingestion, and follow-up automation
- React + Vite + Tailwind primary frontend
- Streamlit kept for internal analytics tooling
- Twilio multichannel outreach (SMS, WhatsApp, voice, email)
- Preference-based customer communication controls

## 1. Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 15+ (optional if using SQLite fallback)
- Ollama with DeepSeek model (recommended)

## 2. Environment
Create `.env.local` from `.env.example` and set at minimum:
- `DATABASE_URL`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`
- `SMTP_*`

Use `.env.local` for developer secrets and keep it out of source control.
`backend/app/main.py` and `backend/app/core/config.py` load `.env.local` first and then `.env` as a fallback.

When using `docker-compose.yml`, set `POSTGRES_PASSWORD` in your shell or env file before startup.

For local SQLite quick start:
- `DATABASE_URL=sqlite:///./imperial_cars.db`

API key requirements for protected endpoints:
- Protected routes (`/api/ask`, `/api/followup*`, `/api/knowledge/*`, `/api/dealership/*`, and related costly routes) require `X-API-Key`.
- Browser fallback is supported through cookie names `imperial_api_key`, `api_key`, or `x_api_key` when headers are not available.

## 3. Install Backend
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 4. Initialize Data
```powershell
.\.venv\Scripts\python.exe scripts\init_db.py
.\.venv\Scripts\python.exe scripts\import_car_data.py
```

If `data/raw/large_cars_dataset.csv` is missing, `import_car_data.py` auto-generates 100 sample cars.

## 5. Run Backend
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8081
```

## 6. Run React Frontend
```powershell
cd frontend-react
npm install
npm run dev
```

Primary interface tabs:
- Chatbot
- Car Database
- Financial Tools
- Paperwork
- Follow-up

## 7. Telegram Bot (Sales Tool)
```powershell
.\.venv\Scripts\python.exe sales_bot.py
```

Use:
- `/followup <customer_id>` to invoke the same `/api/followup/{customer_id}` endpoint used by frontend.

## 8. Follow-up Preference Flow
1. Save preferences via frontend Follow-up tab (SMS/WhatsApp/Email/Voice).
2. Preferences are stored in `customer_channel_prefs`.
3. `POST /api/followup/{customer_id}` generates personalized message with DeepSeek (if no override provided).
4. System sends through all enabled channels and logs outcomes in `followup_log`.

## 9. OCR Pipeline
`backend/app/agents/document_ingestion.py` uses EasyOCR (`easyocr.Reader(['en'])`) and keeps extraction handlers for lead/insurance/cleanup/sold/commission/credit documents.

## 10. Fine-Tuning Workflow
```powershell
.\.venv\Scripts\python.exe scripts\prepare_training_data.py
.\.venv\Scripts\python.exe scripts\download_public_data.py --output data\training\public_qa.jsonl
.\.venv\Scripts\python.exe scripts\finetune_deepseek.py --training_data data\training\imperial_qa.jsonl --epochs 1
```

Fine-tuned adapters are saved to `models/imperial_deepseek`.

## 11. Validation
```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_math.py -q
.\.venv\Scripts\python.exe scripts\full_test.py
```

## 12. Observability
- Health: `GET /api/health`
- API docs: `http://localhost:8081/docs`

## 13. HTTPS Local Testing
Nginx is configured for HTTPS in `deploy/nginx/default.conf` and expects cert files at:
- `deploy/nginx/certs/fullchain.pem`
- `deploy/nginx/certs/privkey.pem`

For local testing, create self-signed certs (see `deploy/nginx/certs/README.md`) and mount them with compose.

## 14. Pre-commit Security Scanning
Install and enable pre-commit hooks:

```powershell
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

The repository uses `gitleaks` plus baseline hooks via `.pre-commit-config.yaml`.
