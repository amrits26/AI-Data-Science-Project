#!/usr/bin/env python
"""Generate Imperial dealership Q&A training data from local CSV files."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_PATH = DATA_DIR / "training" / "imperial_qa.jsonl"


def _read_csv_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _safe(v, fallback: str = "unknown") -> str:
    if v is None:
        return fallback
    text = str(v).strip()
    return text if text else fallback


def _money(v, fallback: float = 0.0) -> float:
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except Exception:
        return float(fallback)


def _build_from_leads(df: pd.DataFrame) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if df.empty:
        return rows

    for _, r in df.iterrows():
        customer = _safe(r.get("customer_name"), "customer")
        vehicle_interest = _safe(r.get("vehicle_interest"), "a vehicle")
        sale_price = _money(r.get("sale_price"), 28000)

        rows.append(
            {
                "instruction": f"How should I follow up with {customer} interested in {vehicle_interest}?",
                "response": (
                    f"Start with a friendly message confirming availability for {vehicle_interest}. "
                    "Offer two appointment windows and include financing pre-qualification support."
                ),
            }
        )
        rows.append(
            {
                "instruction": f"What monthly payment should I quote for a ${sale_price:,.0f} vehicle?",
                "response": (
                    f"At 6.9% APR for 60 months with 10% down, estimate around ${sale_price * 0.0185:,.0f}/month. "
                    "Always confirm with live credit terms before finalizing."
                ),
            }
        )
    return rows


def _build_from_deals(df: pd.DataFrame) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if df.empty:
        return rows

    for _, r in df.iterrows():
        make = _safe(r.get("make"), _safe(r.get("vehicle_make"), "Toyota"))
        model = _safe(r.get("model"), _safe(r.get("vehicle_model"), "Camry"))
        year = _safe(r.get("year"), "2022")
        gross = _money(r.get("gross_profit"), 2500)
        commission = _money(r.get("commission"), gross * 0.2)

        rows.append(
            {
                "instruction": f"Summarize this closed deal: {year} {make} {model}.",
                "response": (
                    f"Deal closed on {year} {make} {model}. Gross profit was ${gross:,.0f} with estimated "
                    f"commission ${commission:,.0f}. Flag this customer for post-sale service follow-up in 30 days."
                ),
            }
        )
        rows.append(
            {
                "instruction": f"How can we improve margin on similar {year} {make} {model} deals?",
                "response": (
                    "Improve margin by tightening appraisal variance, bundling warranty/maintenance products, "
                    "and pre-qualifying financing earlier in the process."
                ),
            }
        )
    return rows


def _build_from_service(df: pd.DataFrame) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if df.empty:
        return rows

    for _, r in df.iterrows():
        customer = _safe(r.get("customer_name"), "customer")
        service_type = _safe(r.get("service_type"), _safe(r.get("event_type"), "maintenance"))
        due = _safe(r.get("due_date"), "soon")

        rows.append(
            {
                "instruction": f"Generate a reminder for {customer} about {service_type} due {due}.",
                "response": (
                    f"Hi {customer}, your {service_type} is due {due}. We can schedule morning or afternoon this week. "
                    "Reply with your preferred time and we will confirm."
                ),
            }
        )
    return rows


def _augment(rows: list[dict[str, str]], target: int) -> list[dict[str, str]]:
    if not rows:
        rows = [
            {
                "instruction": "How should Imperial Cars greet a new lead?",
                "response": "Thank the lead, confirm vehicle interest, offer a test-drive window, and share financing options.",
            }
        ]

    base = list(rows)
    while len(rows) < target:
        sample = random.choice(base)
        rows.append(
            {
                "instruction": sample["instruction"] + " Please keep it concise.",
                "response": sample["response"],
            }
        )
    return rows


def main() -> int:
    random.seed(42)
    deals = _read_csv_or_empty(DATA_DIR / "deals.csv")
    leads = _read_csv_or_empty(DATA_DIR / "leads.csv")
    service_records = _read_csv_or_empty(DATA_DIR / "service_records.csv")

    rows: list[dict[str, str]] = []
    rows.extend(_build_from_deals(deals))
    rows.extend(_build_from_leads(leads))
    rows.extend(_build_from_service(service_records))

    rows = _augment(rows, target=600)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    print(f"Generated {len(rows)} Q&A pairs at {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
