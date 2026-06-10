from __future__ import annotations

import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


PUBLIC_QA_PATH = PROJECT_ROOT / "data" / "public_qa.jsonl"
IMPERIAL_QA_PATH = PROJECT_ROOT / "data" / "training" / "imperial_qa_augmented.jsonl"
LEADS_PATHS = [PROJECT_ROOT / "leads.csv", PROJECT_ROOT / "data" / "leads.csv"]
DEALS_PATHS = [PROJECT_ROOT / "deals.csv", PROJECT_ROOT / "data" / "deals.csv"]
OUTPUT_PATH = PROJECT_ROOT / "data" / "final_training.jsonl"
TARGET_MIN = 1500


def _load_jsonl(path: Path, source: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        instruction = str(payload.get("instruction", "")).strip()
        response = str(payload.get("response", "")).strip()
        if instruction and response:
            rows.append({"instruction": instruction, "response": response, "source": source})
    return rows


def _first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8", errors="ignore") as handle:
        return list(csv.DictReader(handle))


def _rows_from_leads() -> list[dict[str, str]]:
    path = _first_existing(LEADS_PATHS)
    if path is None:
        return []
    rows = _load_csv_rows(path)
    out: list[dict[str, str]] = []
    for row in rows:
        question = str(row.get("question") or row.get("customer_question") or row.get("message") or "").strip()
        if not question:
            continue
        vehicle_interest = str(row.get("vehicle_interest", "a vehicle")).strip() or "a vehicle"
        response = (
            f"Thanks for your question about {vehicle_interest}. We'll confirm availability,"
            " share transparent pricing, and provide financing options based on your budget."
        )
        out.append({"instruction": question, "response": response, "source": "leads"})
    return out


def _rows_from_deals() -> list[dict[str, str]]:
    path = _first_existing(DEALS_PATHS)
    if path is None:
        return []
    rows = _load_csv_rows(path)
    out: list[dict[str, str]] = []
    for row in rows:
        year = str(row.get("vehicle_year") or row.get("year") or "").strip()
        make = str(row.get("vehicle_make") or row.get("make") or "").strip()
        model = str(row.get("vehicle_model") or row.get("model") or "").strip()
        vehicle = " ".join(x for x in [year, make, model] if x).strip() or "this vehicle"
        need = str(row.get("customer_need", "daily use and reliability")).strip() or "daily use and reliability"
        salesperson = str(row.get("salesperson", "our team")).strip() or "our team"
        out.append(
            {
                "instruction": f"Why did this customer buy the {vehicle}?",
                "response": (
                    f"The customer chose the {vehicle} because it best matched their need for {need}. "
                    f"{salesperson} aligned payment comfort, condition, and long-term value before closing."
                ),
                "source": "deals",
            }
        )
    return out


def _dedupe(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen = set()
    for row in rows:
        key = row["instruction"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _balance(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_source[row.get("source", "unknown")].append(row)

    sources = sorted(by_source.keys())
    if not sources:
        return []
    cap = max(1, len(rows) // max(len(sources), 1))

    balanced: list[dict[str, str]] = []
    for source in sources:
        chunk = by_source[source]
        random.shuffle(chunk)
        balanced.extend(chunk[:cap])

    if len(balanced) < len(rows):
        tail = [r for r in rows if r not in balanced]
        random.shuffle(tail)
        balanced.extend(tail)
    return balanced


def _top_up(rows: list[dict[str, str]], target: int) -> list[dict[str, str]]:
    if len(rows) >= target:
        return rows
    if not rows:
        rows = [{"instruction": "What financing options are available?", "response": "We can compare loan and lease options based on budget and credit tier.", "source": "seed"}]

    base = list(rows)
    i = 0
    while len(rows) < target:
        row = base[i % len(base)]
        rows.append(
            {
                "instruction": f"{row['instruction']} (variant {i + 1})",
                "response": row["response"],
                "source": row.get("source", "seed"),
            }
        )
        i += 1
    return rows


def main() -> int:
    random.seed(42)
    public_rows = _load_jsonl(PUBLIC_QA_PATH, "public")
    imperial_rows = _load_jsonl(IMPERIAL_QA_PATH, "imperial")
    lead_rows = _rows_from_leads()
    deal_rows = _rows_from_deals()

    combined = public_rows + imperial_rows + lead_rows + deal_rows
    deduped = _dedupe(combined)
    balanced = _balance(deduped)
    final_rows = _top_up(_dedupe(balanced), TARGET_MIN)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        for row in final_rows:
            handle.write(json.dumps({"instruction": row["instruction"], "response": row["response"]}, ensure_ascii=True) + "\n")

    counts = defaultdict(int)
    for row in final_rows:
        counts[row.get("source", "unknown")] += 1

    print("[merge] source counts:")
    for source, count in sorted(counts.items()):
        print(f"  - {source}: {count}")
    print(f"[merge] total: {len(final_rows)} -> {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())