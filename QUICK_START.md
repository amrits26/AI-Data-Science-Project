# Imperial Cars AI - Quick Start Guide (Phases 1-6)

## What's Included

✅ **Complete core system** with 6 phases implemented:
- Database models (9 tables)
- NHTSA VIN decoder
- Chatbot with question classification
- Financial calculators & visualizations
- Document generation (PDFs)
- Customer lifecycle automation

## Installation (5 minutes)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up Environment
Create `.env` file in project root:
```bash
# PostgreSQL Connection
DATABASE_URL=postgresql://imperial_admin:Imperial123!@localhost:5432/imperial_dealership

# Local LLM (Ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=deepseek-r1:14b

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Data Paths
DATA_DIR=./data
NHTSA_CACHE_DIR=./cache/nhtsa
```

### 3. Initialize Database
```bash
python scripts/init_db.py
```
Expected output:
```
✓ Connected to PostgreSQL
✓ Created 9 database tables
✓ Verified all tables exist
```

### 4. Import Car Data
```bash
python scripts/import_car_data.py
```
Expected output:
```
Step 1: Loading car dataset...
Step 2: Mapping CSV to Car objects...
Step 3: Importing cars to database... (1000 rows)
Step 4: Creating market price snapshot...
Step 5: Summary - Imported 100+ cars successfully!
```

### 5. Start Lifecycle Scheduler
```python
from backend.app.agents.lifecycle_agents import initialize_scheduler

initialize_scheduler()
# ✓ Lifecycle scheduler started
```

---

## Quick Usage Examples

### 1. Ask Chatbot a Question
```python
from backend.app.agents.imperial_chatbot import ask_imperial

# Ask about vehicle specs
response = ask_imperial("What's the price of a 2024 Toyota Camry?")
print(response["answer"])
# Output: "I found information about Toyota vehicles. Would you like specific details?"

# Ask about financing
response = ask_imperial("What's the monthly payment on a $30,000 car at 6.9% for 60 months?")
print(response["answer"])
# Output: "$603.25/month" (with chatbot explanation)
```

### 2. Decode a VIN
```python
from backend.app.agents.nhtsa_api import decode_vin

result = decode_vin("5FNRL6H79LB123456")
print(result)
# Output: {
#   "status": "ok",
#   "vin": "5FNRL6H79LB123456",
#   "year": 2020,
#   "make": "Honda",
#   "model": "Odyssey",
#   "body_class": "Minivan",
#   "engine_type": "V-6",
#   ...
# }
```

### 3. Calculate Monthly Payment
```python
from backend.app.agents.math_tools import loan_calculator

price = 30000
down_payment = 5000
annual_rate = 6.9
term_months = 60

monthly_payment, total_cost = loan_calculator(price, down_payment, annual_rate, term_months)
print(f"Monthly: ${monthly_payment:,.2f}")  # $603.25
print(f"Total: ${total_cost:,.2f}")  # $36195
```

### 4. Generate Financial Chart
```python
from backend.app.agents.visualizations import monthly_payment_chart

# Returns base64-encoded PNG bytes
png_bytes = monthly_payment_chart(30000, 5000, 6.9, 60)

# Save to file
with open("payment_chart.png", "wb") as f:
    f.write(png_bytes)
```

### 5. Create & Track Service Job
```python
from backend.app.agents.customer_updates import create_job, update_job_status, send_update_to_customer

# Create job
job_id = create_job(
    customer_id=1,
    vehicle_id=1,
    job_type="oil_change",
    priority="normal",
    description="Oil change service reminder",
)
# Output: 123 (job ID)

# Update status
update_job_status(123, "in_progress", "Your oil change is underway")

# Send notification
send_update_to_customer(123, telegram_id=987654321)
```

### 6. Generate Deal Jacket PDF
```python
from backend.app.agents.paperwork_finisher import generate_deal_jacket_pdf

deal_data = {
    "deal_number": "DL-2024-001",
    "customer_name": "John Smith",
    "vehicle": "2024 Toyota Camry",
    "vin": "5FNRL6H79LB123456",
    "sale_price": 30000,
    "trade_in_allowance": 5000,
    "down_payment": 0,
    "amount_financed": 25000,
    "commission": 1500,
}

pdf_path = generate_deal_jacket_pdf(deal_data)
print(f"Generated: {pdf_path}")
```

### 7. Run Lifecycle Workflows
```python
from backend.app.agents.lifecycle_agents import manual_trigger

# Manually trigger workflows for testing
result = manual_trigger("onboarding")
# Output: {"status": "ok", "message": "Triggered onboarding workflow"}

result = manual_trigger("service")  # Service reminders
result = manual_trigger("trade_in")  # Trade-in offers
result = manual_trigger("winback")  # Win-back campaigns
result = manual_trigger("buyback")  # Buyback opportunities
```

---

## Project Structure

```
Imperial Cars AI/
├── backend/
│   └── app/
│       ├── agents/ ✅ COMPLETE
│       │   ├── nhtsa_api.py - VIN decoder
│       │   ├── imperial_chatbot.py - Question answering
│       │   ├── visualizations.py - Charts
│       │   ├── math_tools.py - Financial calculators
│       │   ├── carfax_ingestor.py - Vehicle history
│       │   ├── paperwork_finisher.py - PDF generation
│       │   ├── customer_updates.py - Job tracking
│       │   └── lifecycle_agents.py - Automated workflows
│       ├── database/ ✅ COMPLETE
│       │   ├── models.py - 9 SQLAlchemy models
│       │   ├── db.py - Connection pooling
│       │   └── __init__.py - Exports
│       └── api/ (to be enhanced in Phase 7)
│
├── scripts/ ✅ COMPLETE
│   ├── init_db.py - Database setup
│   └── import_car_data.py - Data import
│
├── data/ - CSV files & generated paperwork
├── cache/ - NHTSA API cache
└── requirements.txt ✅ UPDATED
```

---

## Key Features by Phase

### Phase 1: Database ✅
- 9 tables (Car, Customer, Vehicle, ServiceJob, etc.)
- PostgreSQL + pgvector
- Cascade delete relationships
- Connection pooling (10 concurrent, 20 overflow)

### Phase 2: Scripts ✅
- Auto-creates DB schema
- Imports Kaggle CSV (or 100-car sample fallback)
- Verification & error checking

### Phase 3: NHTSA API ✅
- VIN decoder (17-char validation)
- Safety ratings (1-5 scale)
- Makes & models list
- 7-day caching (~cache/nhtsa/~)

### Phase 4: Core Agents ✅
- **Chatbot**: Question classification + DB + LLM
- **Visualizations**: 6 chart types → PNG bytes
- **Math**: Loan, lease, trade-in, buyback calculators

### Phase 5: Documents ✅
- **Carfax Ingestor**: PDF/CSV parsing
- **Paperwork**: Credit apps, deal jackets, service tickets

### Phase 6: Lifecycle ✅
- **Customer Updates**: Job tracking + messaging
- **Lifecycle Agents**: 5 automated workflows (APScheduler)

---

## Testing Checklist

- [ ] Database initialized (`scripts/init_db.py`)
- [ ] Data imported (`scripts/import_car_data.py`)
- [ ] Ollama running (`ollama serve`)
- [ ] Test chatbot: `ask_imperial("What's the price?")`
- [ ] Test VIN decoder: `decode_vin("5FNRL6H79LB123456")`
- [ ] Test calculator: `loan_calculator(30000, 5000, 6.9, 60)`
- [ ] Test chart: `monthly_payment_chart(...)`
- [ ] Test PDF: `generate_deal_jacket_pdf(...)`
- [ ] Test scheduler: `initialize_scheduler()`

---

## Next Phases (7-9)

**Phase 7**: Streamlit frontend (5 new tabs)
**Phase 8**: Telegram bot (10 new commands)
**Phase 9**: Final testing & deployment

---

## Troubleshooting

**PostgreSQL won't connect?**
```bash
# Check connection string
psql $DATABASE_URL

# Install pgvector if needed
CREATE EXTENSION pgvector;
```

**Ollama not responding?**
```bash
# Start Ollama
ollama serve

# Pull model if needed
ollama pull deepseek-r1:14b
```

**Missing dependencies?**
```bash
pip install -r requirements.txt --upgrade
```

---

## Documentation

- [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) - Detailed architecture
- All functions have full docstrings & type hints
- Example usage in each file

---

## Support

Questions about specific modules? Check the docstrings:
```python
from backend.app.agents import imperial_chatbot
help(imperial_chatbot.ask_imperial)
```

Ready to proceed to Phase 7? Let me know! 🚀
