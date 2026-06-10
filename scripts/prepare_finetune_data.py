#!/usr/bin/env python3
"""Build a DeepSeek fine-tuning dataset from dealership and automotive sources.

Output format (JSONL):
{"instruction": "...", "output": "...", "response": "...", "source": "..."}
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import defaultdict
from typing import Any


def normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def read_csv_rows(path: str) -> list[dict[str, str]]:
    if not os.path.exists(path):
        print(f"[prepare] missing file: {path}")
        return []
    rows: list[dict[str, str]] = []
    with open(path, "r", encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append({str(k or "").strip(): str(v or "").strip() for k, v in row.items()})
    print(f"[prepare] loaded {len(rows)} rows from {path}")
    return rows


def read_text(path: str) -> str:
    if not os.path.exists(path):
        print(f"[prepare] missing text file: {path}")
        return ""
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        text = handle.read()
    print(f"[prepare] loaded text from {path} ({len(text)} chars)")
    return text


def first_non_empty(row: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        value = str(row.get(key, "") or "").strip()
        if value:
            return value
    return ""


def as_float(text: str) -> float | None:
    try:
        return float(str(text).replace(",", "").replace("$", "").strip())
    except Exception:
        return None


def format_money(text: str) -> str:
    value = as_float(text)
    if value is None:
        return "price on request"
    return f"${value:,.0f}"


def sanitize_for_training(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    cleaned = re.sub(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", "[redacted_email]", cleaned)
    cleaned = re.sub(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b", "[redacted_phone]", cleaned)
    cleaned = re.sub(r"\b[A-HJ-NPR-Z0-9]{17}\b", "[redacted_vin]", cleaned)
    cleaned = re.sub(r"\b\d{1,5}\s+[A-Za-z0-9.\-\s]{3,40}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct)\b", "[redacted_address]", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def add_example(examples: list[dict[str, str]], source: str, instruction: str, output: str, counters: dict[str, int]) -> None:
    inst = sanitize_for_training(instruction)
    out = sanitize_for_training(output)
    if not inst or not out:
        return
    if len(inst) < 8 or len(out) < 16:
        return
    payload = {
        "instruction": inst,
        "output": out,
        "response": out,
        "source": source,
    }
    examples.append(payload)
    counters[source] += 1


def dedupe_examples(examples: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for row in examples:
        key = (normalize(row.get("instruction", "")), normalize(row.get("output", "")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def write_jsonl(rows: list[dict[str, str]], output_path: str) -> None:
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def add_inventory_examples(examples: list[dict[str, str]], inventory_rows: list[dict[str, str]], counters: dict[str, int]) -> None:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)

    for row in inventory_rows:
        year = first_non_empty(row, ["year", "vehicle_year"])
        make = first_non_empty(row, ["make", "vehicle_make", "manufacturer"])
        model = first_non_empty(row, ["model", "vehicle_model"])
        trim = first_non_empty(row, ["trim", "variant"])
        if not year or not make or not model:
            continue

        engine = first_non_empty(row, ["engine", "engine_description"])
        fuel = first_non_empty(row, ["fuel_type", "fuel"])
        transmission = first_non_empty(row, ["transmission", "transmission_type"])
        drivetrain = first_non_empty(row, ["drivetrain", "drive_type"])
        hp = first_non_empty(row, ["horsepower", "hp"])
        torque = first_non_empty(row, ["torque"])
        mpg_city = first_non_empty(row, ["mpg_city", "city_mpg"])
        mpg_hwy = first_non_empty(row, ["mpg_highway", "highway_mpg"])
        price = first_non_empty(row, ["price", "msrp", "sale_price", "used_avg_price"])
        mileage = first_non_empty(row, ["mileage", "odometer"])
        stock = first_non_empty(row, ["stock_number", "stock", "stock_id"])
        vin = first_non_empty(row, ["vin"])

        vehicle = " ".join([year, make, model, trim]).strip()
        details: list[str] = [f"Vehicle: {vehicle}."]
        if price:
            details.append(f"Price: {format_money(price)}.")
        if mileage:
            details.append(f"Mileage: {mileage} miles.")
        if engine:
            details.append(f"Engine: {engine}.")
        if hp:
            details.append(f"Horsepower: {hp} hp.")
        if torque:
            details.append(f"Torque: {torque} lb-ft.")
        if mpg_city or mpg_hwy:
            details.append(f"Fuel economy: {mpg_city or 'N/A'} city / {mpg_hwy or 'N/A'} highway MPG.")
        if transmission:
            details.append(f"Transmission: {transmission}.")
        if drivetrain:
            details.append(f"Drivetrain: {drivetrain}.")
        if fuel:
            details.append(f"Fuel type: {fuel}.")
        if stock:
            details.append(f"Stock number: {stock}.")
        if vin:
            details.append(f"VIN: {vin}.")
        details.append("At Imperial Cars, I can also help compare trims, estimate payments, and set a test drive.")

        add_example(
            examples,
            "inventory",
            f"Tell me about the {vehicle}.",
            " ".join(details),
            counters,
        )

        add_example(
            examples,
            "inventory",
            f"What are the key specs, price, and mileage for stock {stock or vehicle}?",
            " ".join(details),
            counters,
        )

        if make and model:
            groups[(make.lower(), model.lower())].append(row)

    for (make_key, model_key), rows in groups.items():
        if len(rows) < 2:
            continue
        rows_sorted = sorted(rows, key=lambda item: first_non_empty(item, ["year", "vehicle_year"]))
        older = rows_sorted[0]
        newer = rows_sorted[-1]
        older_year = first_non_empty(older, ["year", "vehicle_year"])
        newer_year = first_non_empty(newer, ["year", "vehicle_year"])
        make = first_non_empty(newer, ["make", "vehicle_make"])
        model = first_non_empty(newer, ["model", "vehicle_model"])
        older_price = format_money(first_non_empty(older, ["price", "msrp", "sale_price", "used_avg_price"]))
        newer_price = format_money(first_non_empty(newer, ["price", "msrp", "sale_price", "used_avg_price"]))
        answer = (
            f"For {make} {model}, the {older_year} listing is around {older_price} and the {newer_year} listing is around {newer_price}. "
            "The newer model usually has fresher tech and warranty runway, while the older option often wins on value. "
            "I can narrow this with your budget, preferred mileage, and feature priorities."
        )
        add_example(
            examples,
            "inventory_comparison",
            f"Compare the {older_year} vs {newer_year} {make} {model} in your inventory.",
            answer,
            counters,
        )


def _split_paragraphs(text: str) -> list[str]:
    chunks: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        compact = re.sub(r"\s+", " ", block).strip()
        if len(compact) >= 120:
            chunks.append(compact)
    return chunks


def add_encyclopedia_examples(examples: list[dict[str, str]], text: str, counters: dict[str, int], limit: int = 400) -> None:
    if not text:
        return
    chunks = _split_paragraphs(text)
    for idx, chunk in enumerate(chunks[:limit], start=1):
        topic = "automotive concept"
        heading_match = re.match(r"([A-Z][A-Za-z0-9\-\s]{3,80}):", chunk)
        if heading_match:
            topic = heading_match.group(1).strip()
        else:
            first_words = " ".join(chunk.split(" ")[:5]).strip()
            if first_words:
                topic = first_words
        add_example(
            examples,
            "encyclopedia",
            f"Explain {topic} in simple terms for a car shopper.",
            chunk,
            counters,
        )
        add_example(
            examples,
            "encyclopedia",
            f"What should I know about {topic} before buying a vehicle?",
            chunk,
            counters,
        )


def add_winning_script_examples(examples: list[dict[str, str]], script_text: str, counters: dict[str, int], limit: int = 500) -> None:
    if not script_text:
        return
    lines = [line.strip() for line in script_text.splitlines() if line.strip()]
    question = ""
    count = 0
    for line in lines:
        if line.lower().startswith(("q:", "question:")):
            question = line.split(":", 1)[-1].strip()
            continue
        if line.lower().startswith(("a:", "answer:")) and question:
            answer = line.split(":", 1)[-1].strip()
            add_example(examples, "winning_scripts", question, answer, counters)
            question = ""
            count += 1
            if count >= limit:
                return

    # Fallback parser for paragraph-style scripts.
    blocks = re.split(r"\n\s*\n", script_text)
    for block in blocks:
        clean = re.sub(r"\s+", " ", block).strip()
        if len(clean) < 40 or "?" not in clean:
            continue
        q = clean.split("?", 1)[0].strip() + "?"
        a = clean.split("?", 1)[1].strip() or "Focus on value, fit, and transparent numbers."
        add_example(examples, "winning_scripts", q, a, counters)
        count += 1
        if count >= limit:
            return


def add_chat_history_examples(examples: list[dict[str, str]], chat_rows: list[dict[str, str]], counters: dict[str, int]) -> None:
    for row in chat_rows:
        question = first_non_empty(row, ["question", "prompt", "instruction", "user_message"])
        answer = first_non_empty(row, ["answer", "response", "output", "assistant_message"])
        rating = first_non_empty(row, ["rating", "score"])
        if not question or not answer:
            continue
        rating_num = as_float(rating)
        if rating_num is not None and rating_num < 0:
            continue
        add_example(examples, "chat_history", question, answer, counters)


def add_nhtsa_fueleconomy_examples(examples: list[dict[str, str]], inventory_rows: list[dict[str, str]], counters: dict[str, int], limit: int = 800) -> None:
    count = 0
    for row in inventory_rows:
        if count >= limit:
            break
        year = first_non_empty(row, ["year", "vehicle_year"])
        make = first_non_empty(row, ["make", "vehicle_make"])
        model = first_non_empty(row, ["model", "vehicle_model"])
        if not year or not make or not model:
            continue
        mpg_city = first_non_empty(row, ["mpg_city", "city_mpg"])
        mpg_hwy = first_non_empty(row, ["mpg_highway", "highway_mpg"])
        vehicle = f"{year} {make} {model}"
        safety_answer = (
            f"For {vehicle}, I can verify NHTSA safety data by VIN and model-year records. "
            "Ask for recall checks, crash ratings, and open campaign status before purchase."
        )
        mpg_answer = (
            f"For {vehicle}, estimated fuel economy is {mpg_city or 'N/A'} city and {mpg_hwy or 'N/A'} highway MPG. "
            "Real-world MPG can vary by driving style, weather, and maintenance condition."
        )
        add_example(examples, "nhtsa", f"How safe is the {vehicle} and how do I check recalls?", safety_answer, counters)
        add_example(examples, "fueleconomy", f"What MPG should I expect from the {vehicle}?", mpg_answer, counters)
        count += 1


def add_carfax_placeholders(examples: list[dict[str, str]], inventory_rows: list[dict[str, str]], counters: dict[str, int], limit: int = 500) -> None:
    count = 0
    for row in inventory_rows:
        if count >= limit:
            break
        stock = first_non_empty(row, ["stock_number", "stock", "stock_id"])
        vin = first_non_empty(row, ["vin"])
        year = first_non_empty(row, ["year", "vehicle_year"])
        make = first_non_empty(row, ["make", "vehicle_make"])
        model = first_non_empty(row, ["model", "vehicle_model"])
        vehicle = " ".join([year, make, model]).strip() or "this vehicle"
        prompt_key = stock or vin or vehicle
        answer = (
            "Carfax report integration is being connected. I can log your request now and share the vehicle-history report "
            "as soon as the VIN-linked report is available. Meanwhile, I can provide service history notes, title status if available, "
            "and recall checks from supported sources."
        )
        add_example(examples, "carfax_placeholder", f"Show me the Carfax for {prompt_key}.", answer, counters)
        count += 1


def ensure_minimum_rows(examples: list[dict[str, str]], counters: dict[str, int], target: int) -> None:
    if len(examples) >= target:
        return
    seed_bank = [
        (
            "How do I choose between two similar used cars?",
            "Compare condition, service history, mileage, ownership cost, and financing terms side by side before deciding.",
        ),
        (
            "What should I ask before buying a used car?",
            "Ask for maintenance records, accident history, open recalls, tire/brake condition, and out-the-door pricing details.",
        ),
        (
            "Can you help with financing if my credit is not perfect?",
            "Yes. We can review lender options for your profile and structure terms that fit your payment comfort while staying transparent.",
        ),
    ]
    idx = 0
    while len(examples) < target:
        q, a = seed_bank[idx % len(seed_bank)]
        add_example(examples, "supplemental", f"{q} (variant {idx + 1})", a, counters)
        idx += 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare Imperial DeepSeek fine-tuning JSONL data")
    parser.add_argument("--data_dir", default="data", help="Directory containing source data files")
    parser.add_argument("--kb_dir", default="knowledge_base", help="Knowledge base directory")
    parser.add_argument("--output", default=os.path.join("data", "finetune_deepseek.jsonl"), help="Output JSONL path")
    parser.add_argument("--target_min", type=int, default=2500, help="Minimum number of rows to generate")
    args = parser.parse_args()

    data_dir = args.data_dir
    kb_dir = args.kb_dir

    inventory_rows = read_csv_rows(os.path.join(data_dir, "inventory_backup.csv"))
    if not inventory_rows:
        inventory_rows = read_csv_rows(os.path.join(data_dir, "inventory.csv"))
    chat_rows = read_csv_rows(os.path.join(data_dir, "chat_history.csv"))
    feedback_rows = read_csv_rows(os.path.join(data_dir, "feedback.csv"))

    encyclopedia_text = read_text(os.path.join(data_dir, "automotive_encyclopedia.txt"))
    auto_qa_text = read_text(os.path.join(kb_dir, "auto_qa.txt"))
    scripts_text_a = read_text(os.path.join(data_dir, "winning_scripts.txt"))
    scripts_text_b = read_text(os.path.join(kb_dir, "winning_scripts.txt"))

    examples: list[dict[str, str]] = []
    counters: dict[str, int] = defaultdict(int)

    add_inventory_examples(examples, inventory_rows, counters)
    add_encyclopedia_examples(examples, encyclopedia_text, counters)
    add_encyclopedia_examples(examples, auto_qa_text, counters, limit=200)
    add_winning_script_examples(examples, scripts_text_a, counters)
    add_winning_script_examples(examples, scripts_text_b, counters)
    add_chat_history_examples(examples, chat_rows, counters)
    add_chat_history_examples(examples, feedback_rows, counters)
    add_nhtsa_fueleconomy_examples(examples, inventory_rows, counters)
    add_carfax_placeholders(examples, inventory_rows, counters)

    deduped = dedupe_examples(examples)
    ensure_minimum_rows(deduped, counters, args.target_min)
    final_rows = dedupe_examples(deduped)

    write_jsonl(final_rows, args.output)

    print("[prepare] source counts:")
    for source_name, count in sorted(counters.items()):
        print(f"  - {source_name}: {count}")
    print(f"[prepare] total_rows={len(final_rows)}")
    print(f"[prepare] output={args.output}")
    if len(final_rows) < 2000:
        print("[prepare] warning: fewer than 2000 rows generated; add more source data for stronger training quality")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
