# 📊 AI Data Scientist

A system where you upload any CSV and get **senior data scientist–style** analysis: profiling, EDA, statistical structure, anomalies, modeling recommendations, and an executive summary — in under a few seconds.

**Vibe:** *"I just hired a data scientist for 10 seconds."*

---

## What it does

1. **Profiles the dataset** — dtypes, missing %, skewness, kurtosis, cardinality, class imbalance, leakage indicators, and a **data health score**.
2. **Runs intelligent EDA** — correlation matrix, mutual information, PCA variance, IQR outliers, distribution fitting and transform suggestions (e.g. “Feature ‘income’ is highly right-skewed. Log transform recommended.”).
3. **Detects statistical structure** — high correlations, multicollinearity hints, feature clustering (PCA).
4. **Identifies anomalies** — Isolation Forest, Z-score, DBSCAN; summarizes e.g. “X% of data points exhibit high-leverage anomaly patterns.”
5. **Suggests modeling strategies** — classification and regression using **RandomForest** ensembles; cross-validation, feature importance, SHAP explainability, and overfitting detection. Other models (Logistic, XGBoost, LightGBM) planned for future releases.
6. **Explains in natural language** — executive summary, business implications, risks, next steps (template or LLM if `OPENAI_API_KEY` is set).
7. **Cognitive flags** — data leakage risk, Simpson’s paradox possibility, multicollinearity, high cardinality, small sample bias, feature dominance, overfitting risk.
8. **Lead sheet ingestion (OCR)** — upload paper lead photos, extract customer details, and store structured leads in `DATA_DIR/leads.csv`.
9. **Dealership tools** — lead scoring, trade-in appraisal, and daily briefing endpoints for sales workflows.
10. **Local Telegram sales bot** — async bot using Ollama only (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`) for private conversational support.

---

# 🚗 Imperial Cars AI System

**A complete, local-first AI dealership platform** with DeepSeek chatbot, financial calculators, document generation, and automated customer lifecycle management.

**Status**: ✅ Phases 1-6 Complete (67% done) | 🔄 Phases 7-9 Ready

---

## 🎯 What You Get

### ✅ Core System (Phases 1-6 Complete)

- **AI Chatbot** - Answer customer questions about specs, pricing, financing, trade-ins
- **Financial Calculators** - Loan, lease, trade-in equity, break-even analysis
- **Interactive Charts** - Payment schedules, depreciation curves, comparisons
- **Document Generation** - Credit applications, deal jackets, service tickets (PDFs)
- **Vehicle History** - NHTSA VIN decoder with safety ratings
- **Automated Campaigns** - Welcome, service reminders, trade-in offers, win-back, buyback
- **Job Tracking** - Service maintenance with Telegram notifications
- **Local & Private** - Runs 100% locally, zero cloud dependencies, you own all data

### 🔄 Coming Next (Phases 7-9)

- **Streamlit Dashboard** - 5 interactive tabs for customers & admins
- **Telegram Bot** - 10 new commands for instant interactions
- **Production Ready** - Security, monitoring, Docker deployment

---

## ⚡ Quick Start (5 minutes)

### 1. Install
```bash
pip install -r requirements.txt
```

### 2. Configure
Create `.env`:
```bash
DATABASE_URL=postgresql://imperial_admin:Imperial123!@localhost:5432/imperial_dealership
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=deepseek-r1:14b
TELEGRAM_BOT_TOKEN=your_token_here
```

### 3. Setup Database
```bash
python scripts/init_db.py
python scripts/import_car_data.py
```

### 4. Test Everything
```bash
python scripts/test_all.py
```

### 5. Start Using
```python
from backend.app.agents.imperial_chatbot import ask_imperial

response = ask_imperial("What's the price of a Toyota Camry?")
print(response["answer"])
```

**See [QUICK_START.md](QUICK_START.md) for complete examples.**

Run:

```bash
python sales_bot.py
```

Bot commands:

- `/briefing`
- `/scoreleads`
- `/appraise Toyota Camry 2020 35000 good`
- `/payout STOCK123`

Photo ingestion in Telegram: send a photo with caption exactly one of `lead`, `insurance`, `cleanup`, `sold`, `commission`, `credit`.

---

## Optional: LLM executive summary

For an LLM-generated executive summary instead of the template:

1. Copy `.env.example` to `.env`.
2. Set `OPENAI_API_KEY=your_key` (and optionally `OPENAI_API_BASE`, `OPENAI_MODEL`).

If the key is not set, the app still runs and uses a **template-based** summary.

For OCR + bot conversational workflow, Ollama is used locally (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`) and no cloud LLM key is required.

---

## Project layout

## New Phase 4-5 Modules (Implemented)

- `backend/app/agents/inventory_scraper.py`: polite inventory crawler with `robots.txt` checks, pagination, detail parsing, and `data/inventory.csv` export.
- `backend/app/agents/vehicle_intel.py`: vehicle lookup by stock/VIN, similar vehicles, photo extraction, and optional Carfax PDF summary.
- `backend/app/agents/finance_agent.py`: payment ladder by down payment, APR tiering, objection handling scripts.
- `backend/app/agents/negotiation.py`: negotiation intent detection and script response generation.
- `backend/app/agents/payout_generator.py`: commission and payout calculator.
- `backend/app/agents/knowledge_base/ingest.py` and `backend/app/agents/knowledge_base/query.py`: optional local FAISS RAG ingest/query for dealership docs.
- `frontend/pages/sales_copilot.py`: unified Streamlit UI for inventory intel, finance, negotiation, payout, and knowledge query.

## New API Endpoints

- `POST /api/dealership/scrape-inventory`
- `POST /api/dealership/vehicle-intel`
- `POST /api/dealership/similar-vehicles`
- `GET /api/dealership/vehicle-photos/{stock_number}`
- `POST /api/dealership/finance-ladder`
- `POST /api/dealership/negotiation-assist`
- `POST /api/dealership/payout`
- `POST /api/dealership/lead-quality`
- `POST /api/dealership/sales-stage`
- `POST /api/knowledge/ingest`
- `POST /api/knowledge/query`

```
├── backend/
│   └── app/
│       ├── main.py           # FastAPI app
│       ├── api/routes.py     # POST /api/analyze
│       ├── agents/
│       │   ├── profiler.py           # Data profiler + health score
│       │   ├── statistical.py       # Correlation, PCA, MI, outliers, distributions
│       │   ├── modeling.py           # Classification / regression / clustering + SHAP
│       │   ├── anomaly.py            # Isolation Forest, Z-score, DBSCAN
│       │   ├── cognitive_flags.py   # Leakage, Simpson, multicollinearity, etc.
│       │   └── insight_generator.py # Executive summary (template or LLM)
│       │   ├── document_ingestion.py # OCR lead extraction + CSV persistence
│       │   └── dealership_tools.py   # Lead scoring, trade-in appraisal, daily briefing
│       ├── core/config.py
│       └── schemas/
├── frontend/
│   └── app.py                # Streamlit UI (Data Story + Technical mode, insight cards)
├── sales_bot.py              # Async Telegram bot + Ollama integration
├── requirements.txt
├── .env.example
└── README.md
```

---

## Tech stack

- **Backend:** FastAPI, Pandas, NumPy, SciPy, scikit-learn (RandomForest-first), SHAP.
- **Frontend:** Streamlit, Plotly.
- **OCR & Bot:** pytesseract, Pillow, python-telegram-bot, httpx.
- **Optional:** OpenAI/Anthropic API for executive summary. Ollama for local dealership assistant workflows.

---

## Killer features

- **Cognitive flags** — leakage, Simpson’s paradox, multicollinearity, high cardinality, small sample bias, feature dominance, overfitting.
- **Data Story Mode** — toggle: Technical (full stats) vs Executive (plain English).
- **Interactive insight cards** — each flag expandable with recommendation and math explanation.

You can extend with: Bayesian inference, drift detection, fairness metrics, or LangGraph for multi-agent reasoning.
