# Imperial Cars AI - Roadmap for Phases 7-9

**Current Status**: Phases 1-6 ✅ Complete (67% of system)

**Next Steps**: Frontend, Bot, & Deployment (Phases 7-9, 33% remaining)

---

## Phase 7: Streamlit Frontend Expansion (4-5 hours)

### Goal
Add 5 new tabs to existing Streamlit app with interactive visualizations and data dashboards.

### Files to Modify
- [frontend/app.py](frontend/app.py) - Add new tabs

### New Tabs

#### Tab 1: 🔍 Vehicle Specs & Search
**Features**:
- Search cars by make/model/year
- Display spec comparison table
- Show safety ratings (NHTSA)
- Display depreciation curve chart

**Code Pattern**:
```python
st.subheader("Vehicle Specifications")
make = st.text_input("Enter make (e.g., Toyota)")
model = st.text_input("Enter model (e.g., Camry)")

if st.button("Search"):
    from backend.app.database import get_db_session, Car
    db = get_db_session()
    cars = db.query(Car).filter(
        Car.make.ilike(make),
        Car.model.ilike(model)
    ).limit(10).all()
    
    df = pd.DataFrame([{
        "Year": c.year,
        "Make": c.make,
        "Model": c.model,
        "MSRP": f"${c.msrp:,.0f}",
        "HP": c.horsepower,
        "MPG": c.mpg_highway,
    } for c in cars])
    
    st.dataframe(df)
```

#### Tab 2: 💰 Pricing & Financing
**Features**:
- Loan calculator with slider inputs
- Monthly payment chart
- Comparison: lease vs buy
- Trade-in equity calculator

**Code Pattern**:
```python
st.subheader("Financing Options")
col1, col2 = st.columns(2)

with col1:
    price = st.number_input("Vehicle Price", value=30000, step=1000)
    down = st.number_input("Down Payment", value=5000, step=1000)

with col2:
    rate = st.slider("Interest Rate %", 0.0, 10.0, 6.9)
    term = st.select_slider("Loan Term (months)", [24, 36, 48, 60, 72])

from backend.app.agents.math_tools import loan_calculator
monthly, total = loan_calculator(price, down, rate, term)

st.metric("Monthly Payment", f"${monthly:,.2f}")
st.metric("Total Cost", f"${total:,.2f}")

# Show chart
from backend.app.agents.visualizations import monthly_payment_chart
png_b64 = monthly_payment_chart(price, down, rate, term)
st.image(png_b64, width=700)
```

#### Tab 3: 🚗 My Service Jobs
**Features**:
- Display pending/completed jobs for logged-in customer
- Job status timeline
- Schedule new maintenance
- Receive notifications

**Code Pattern**:
```python
st.subheader("Service Reminders")

# Get current customer (would need auth integration)
customer_id = st.session_state.get("customer_id", 1)

from backend.app.agents.customer_updates import get_customer_jobs
jobs = get_customer_jobs(customer_id)

for job in jobs:
    with st.expander(f"{job['job_type'].replace('_', ' ').title()} - {job['status'].upper()}"):
        st.write(f"Priority: {job['priority']}")
        st.write(f"Due: {job['due_date']}")
        if st.button(f"Schedule {job['id']}"):
            st.success("Appointment scheduled!")
```

#### Tab 4: 📊 Customer Lifecycle Dashboard
**Features**:
- View sent campaigns (welcome, service reminders, trade-in offers, etc.)
- Campaign effectiveness metrics
- Next scheduled outreach
- Manual trigger workflows (for testing)

**Code Pattern**:
```python
st.subheader("Your Engagement Timeline")

customer_id = st.session_state.get("customer_id", 1)
from backend.app.agents.lifecycle_agents import get_nurture_history

history = get_nurture_history(customer_id)

for log in history:
    st.info(f"📧 {log['campaign_type'].replace('_', ' ').title()} - {log['sent_at'].strftime('%m/%d/%Y')}")

# Admin: Manual trigger
if st.session_state.get("is_admin"):
    st.subheader("Admin: Manual Workflows")
    workflow = st.selectbox("Trigger workflow", ["onboarding", "service", "trade_in", "winback", "buyback"])
    
    if st.button("Execute"):
        from backend.app.agents.lifecycle_agents import manual_trigger
        result = manual_trigger(workflow)
        st.success(result["message"])
```

#### Tab 5: 📈 Sales Dashboard (Admin)
**Features**:
- Active deals summary
- Revenue metrics
- Salesperson performance
- Pending jobs by priority
- Report generation

**Code Pattern**:
```python
if not st.session_state.get("is_admin"):
    st.error("Admin only")
else:
    st.subheader("Sales Dashboard")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("This Month Sales", "$450,000")
    col2.metric("Pending Deals", "12")
    col3.metric("Avg Commission", "$3,500")
    
    # Chart: Sales by salesperson
    st.bar_chart({"John": 50000, "Maria": 45000, "James": 40000})
    
    # Table: Pending jobs
    from backend.app.agents.customer_updates import get_pending_jobs
    jobs = get_pending_jobs()
    st.dataframe(jobs)
```

### Dependencies
- streamlit (already installed)
- plotly (already installed)
- pandas (already installed)

### Estimated Time: 4-5 hours

---

## Phase 8: Telegram Bot Enhancement (3-4 hours)

### Goal
Add 10 new commands to Telegram bot for customer engagement.

### File to Modify
- [sales_bot.py](sales_bot.py) - Add new command handlers

### New Commands

#### 1. `/ask` - Ask Chatbot
```python
@bot.message_handler(commands=['ask'])
def handle_ask(message):
    question = message.text.replace("/ask ", "")
    from backend.app.agents.imperial_chatbot import ask_imperial
    response = ask_imperial(question)
    bot.send_message(message.chat.id, response["answer"])
```

#### 2. `/specs` - Vehicle Specifications
```python
@bot.message_handler(commands=['specs'])
def handle_specs(message):
    make = message.text.replace("/specs ", "").split()[0]
    from backend.app.database import get_db_session, Car
    db = get_db_session()
    cars = db.query(Car).filter(Car.make.ilike(make)).limit(3).all()
    
    for car in cars:
        text = f"*{car.year} {car.make} {car.model}*\n"
        text += f"MSRP: ${car.msrp:,.0f}\n"
        text += f"Engine: {car.engine} ({car.horsepower}hp)\n"
        text += f"MPG: {car.mpg_highway} hwy"
        bot.send_message(message.chat.id, text, parse_mode="markdown")
```

#### 3. `/compare` - Compare Vehicles
```python
@bot.message_handler(commands=['compare'])
def handle_compare(message):
    args = message.text.replace("/compare ", "").split(" vs ")
    car1, car2 = args[0].strip(), args[1].strip() if len(args) > 1 else None
    
    # Fetch from DB and compare
    bot.send_message(message.chat.id, "Comparison chart: [displays chart]")
```

#### 4. `/price_check` - Get Vehicle Pricing
```python
@bot.message_handler(commands=['price_check'])
def handle_price_check(message):
    make_model = message.text.replace("/price_check ", "")
    from backend.app.database import get_db_session, Car
    db = get_db_session()
    cars = db.query(Car).filter(
        Car.make.ilike(make_model.split()[0])
    ).all()
    
    prices = [f"${c.msrp:,.0f}" for c in cars if c.msrp]
    bot.send_message(message.chat.id, f"Prices: {', '.join(prices)}")
```

#### 5. `/trade_in_quote` - Get Trade-In Value
```python
@bot.message_handler(commands=['trade_in_quote'])
def handle_trade_in_quote(message):
    bot.send_message(
        message.chat.id,
        "📸 Send a photo of your vehicle or provide VIN (17 chars)"
    )
    bot.register_next_step_handler(message, process_trade_in_photo)

def process_trade_in_photo(message):
    if message.content_type == "photo":
        # Process photo (would need OCR for VIN extraction)
        pass
    elif len(message.text) == 17:
        from backend.app.agents.nhtsa_api import decode_vin
        vin_data = decode_vin(message.text)
        # Estimate trade-in value
        bot.send_message(message.chat.id, f"Your vehicle: {vin_data['year']} {vin_data['make']} {vin_data['model']}")
```

#### 6. `/payment_calc` - Calculate Monthly Payment
```python
@bot.message_handler(commands=['payment_calc'])
def handle_payment_calc(message):
    bot.send_message(message.chat.id, "Enter vehicle price (e.g., 30000)")
    bot.register_next_step_handler(message, process_price)

def process_price(message):
    price = float(message.text)
    bot.send_message(message.chat.id, "Enter down payment (e.g., 5000)")
    bot.register_next_step_handler(message, lambda m: process_down_payment(m, price))

def process_down_payment(message, price):
    down = float(message.text)
    from backend.app.agents.math_tools import loan_calculator
    monthly, total = loan_calculator(price, down, 6.9, 60)
    bot.send_message(message.chat.id, f"Monthly: ${monthly:,.2f}\nTotal: ${total:,.2f}")
```

#### 7. `/show_chart` - Display Financial Charts
```python
@bot.message_handler(commands=['show_chart'])
def handle_show_chart(message):
    from backend.app.agents.visualizations import monthly_payment_chart
    import requests
    
    png_b64 = monthly_payment_chart(30000, 5000, 6.9, 60)
    # Save PNG and send
    with open("temp.png", "wb") as f:
        f.write(png_b64)
    
    with open("temp.png", "rb") as f:
        bot.send_photo(message.chat.id, f)
```

#### 8. `/my_jobs` - View Service Reminders
```python
@bot.message_handler(commands=['my_jobs'])
def handle_my_jobs(message):
    customer_id = get_customer_from_telegram(message.chat.id)
    from backend.app.agents.customer_updates import get_customer_jobs
    jobs = get_customer_jobs(customer_id)
    
    text = "📋 Your Service Jobs:\n\n"
    for job in jobs:
        text += f"• {job['job_type'].replace('_', ' ').title()} ({job['status']})\n"
    
    bot.send_message(message.chat.id, text)
```

#### 9. `/schedule_test_drive` - Book Appointment
```python
@bot.message_handler(commands=['schedule_test_drive'])
def handle_schedule(message):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add("Today", "Tomorrow", "This Weekend")
    bot.send_message(message.chat.id, "When?", reply_markup=markup)
    bot.register_next_step_handler(message, process_test_drive_date)

def process_test_drive_date(message):
    # Store appointment and notify salesperson
    bot.send_message(message.chat.id, "✓ Test drive scheduled!")
```

#### 10. `/help` - Show All Commands
```python
@bot.message_handler(commands=['help'])
def handle_help(message):
    help_text = """
    🚗 *Imperial Cars Bot Commands*
    
    /ask - Ask a question
    /specs - Get vehicle specs
    /compare - Compare two cars
    /price_check - Check pricing
    /trade_in_quote - Trade-in estimate
    /payment_calc - Calculate payment
    /show_chart - Display charts
    /my_jobs - Service reminders
    /schedule_test_drive - Book appointment
    /help - This message
    """
    bot.send_message(message.chat.id, help_text, parse_mode="markdown")
```

### Dependencies
- python-telegram-bot (already installed)
- requests (already installed)

### Estimated Time: 3-4 hours

---

## Phase 9: Final Configuration & Testing (2-3 hours)

### Goal
Production hardening, documentation, and deployment preparation.

### Tasks

#### 1. Security Hardening
```python
# Add to config.py or main.py
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# CORS whitelist
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted hosts
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[".imperialcars.local", "localhost"],
)
```

#### 2. Logging & Monitoring
```python
import logging
from pythonjsonlogger import jsonlogger

# JSON logging for production
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)
```

#### 3. Performance Testing
```bash
# Load test with locust
pip install locust

# Create locustfile.py
from locust import HttpUser, task, between

class ImperialCarsUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def ask_chatbot(self):
        self.client.post("/api/ask", json={"question": "What's a Toyota Camry?"})
    
    @task
    def decode_vin(self):
        self.client.get("/api/vin/decode/5FNRL6H79LB123456")
```

#### 4. Database Optimization
```sql
-- Create indexes for common queries
CREATE INDEX idx_car_make_model ON car(make, model);
CREATE INDEX idx_car_year ON car(year);
CREATE INDEX idx_customer_created ON customer(created_at);
CREATE INDEX idx_service_job_status ON service_job(status);
```

#### 5. API Documentation
- Generate with FastAPI Swagger: `/docs`
- Export OpenAPI spec for integration partners

#### 6. Deployment Configuration
```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 7. CI/CD Pipeline
```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - run: pip install -r requirements.txt
      - run: python scripts/test_all.py
```

### Estimated Time: 2-3 hours

---

## Summary Timeline

| Phase | Name | Duration | Status |
|-------|------|----------|--------|
| 1 | Database | ✅ Complete | ✅ |
| 2 | Scripts | ✅ Complete | ✅ |
| 3 | NHTSA API | ✅ Complete | ✅ |
| 4 | Core Agents | ✅ Complete | ✅ |
| 5 | Documents | ✅ Complete | ✅ |
| 6 | Lifecycle | ✅ Complete | ✅ |
| **7** | **Frontend** | **4-5 hrs** | 🔄 Next |
| **8** | **Telegram Bot** | **3-4 hrs** | 🔄 Next |
| **9** | **Production** | **2-3 hrs** | 🔄 Next |

**Total Remaining**: ~10 hours of development

---

## Ready to Continue?

To start **Phase 7 (Streamlit Frontend)**:

1. Let me know you're ready
2. I'll create the new Streamlit tabs
3. We'll test each tab integration
4. Then move to Phase 8 & 9

**Current System**:
- ✅ 9 database tables
- ✅ 8 core agents (chatbot, visualizations, math, carfax, paperwork, updates, lifecycle)
- ✅ NHTSA integration with caching
- ✅ Fully automated lifecycle campaigns
- ✅ PDF document generation
- ✅ All financial calculators

**Remaining**:
- 🔄 Streamlit frontend expansion
- 🔄 Telegram bot enhancements
- 🔄 Production hardening & testing

---

## Reference Documentation

- [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) - Detailed architecture
- [QUICK_START.md](QUICK_START.md) - Quick reference
- [scripts/test_all.py](scripts/test_all.py) - Comprehensive test suite

---

Let me know when you're ready to proceed! 🚀
