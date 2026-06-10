# 🚗 Car Guru – Imperial Cars AI Dealership Assistant

A production‑ready, local‑first AI platform for car dealerships. It combines a chatbot, live inventory search, financial calculators, document generation, and customer lifecycle automation – all running on your own infrastructure.

## ✨ Features

- **AI Chatbot** – Answers customer questions about specs, pricing, financing, trade‑ins.
- **Live Car Finder** – Scans ImperialCars.com for 2500‑class trucks with heated seats (or any custom query).
- **Financial Tools** – Loan & lease calculators, trade‑in equity, break‑even analysis.
- **Document Generation** – PDF credit apps, deal jackets, service tickets.
- **Vehicle Intel** – NHTSA VIN decoder, safety ratings, recall checks.
- **Automated Campaigns** – Welcome, service reminders, trade‑in offers, win‑back.
- **Observability** – Health checks, heartbeat logging, watchdog alerts.
- **Local & Private** – Zero cloud dependencies; you own all data.

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL (optional, falls back to SQLite)
- Ollama (for local LLM, or use DeepSeek API)

### Installation

```bash
# Clone the repository
git clone https://github.com/amrits26/AI-Data-Science-Project.git
cd AI-Data-Science-Project

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your keys (see below)
