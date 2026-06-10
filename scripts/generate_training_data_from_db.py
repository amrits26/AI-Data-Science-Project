#!/usr/bin/env python
"""Generate large Imperial-specific training Q&A data from cars table."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import defaultdict
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from backend.app.database.db import get_db_session
from backend.app.database.models import Car

OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "training", "imperial_qa_augmented.jsonl")

IMPERIAL_FLAIR = [
    "Come test drive at Imperial Cars in Mendon, MA.",
    "Visit Imperial Cars in Mendon, MA for a same-day test drive.",
    "Our Imperial Cars team in Mendon, MA can help you compare trims in person.",
    "Ask about current Imperial Cars specials when you visit our Mendon, MA showroom.",
]

BRAND_GENERAL_BANK = {
    "BMW": [
        (
            "Are BMWs expensive to maintain?",
            "BMW service can cost more than mainstream brands, but our certified pre-owned BMW inventory includes warranty options that help cover major repairs and reduce out-of-pocket surprises.",
        ),
        (
            "Is buying a used BMW a good idea?",
            "A well-maintained used BMW can be a great value. We inspect condition, verify service history, and help you choose a protection plan that matches your budget.",
        ),
        (
            "Which BMW is best for a daily commute?",
            "Most shoppers choose 3 Series and X3 trims for a balance of comfort, efficiency, and performance. We can match you to a trim based on your commute and budget.",
        ),
    ],
    "MERCEDES": [
        (
            "Are Mercedes-Benz vehicles reliable?",
            "Many Mercedes-Benz models are dependable when properly maintained. We review maintenance records and offer warranty-backed options to improve ownership confidence.",
        ),
        (
            "Should I buy a used Mercedes or lease new?",
            "If you want lower monthly cost and slower depreciation, certified pre-owned is often a smart move. If you want the latest tech every few years, leasing may fit better.",
        ),
    ],
    "TESLA": [
        (
            "How long does it take to charge a Tesla at home?",
            "With Level 2 charging, many Tesla owners add meaningful range overnight. We also walk buyers through charger options and installation steps.",
        ),
        (
            "Is Tesla battery degradation a concern?",
            "Modern Tesla batteries are designed for long life. We explain real-world battery health factors and help you evaluate mileage and usage history before purchase.",
        ),
    ],
    "TOYOTA": [
        (
            "Are Toyotas good for long-term ownership?",
            "Toyota is a popular long-term ownership brand thanks to strong reliability and resale value. We can recommend trims with the best maintenance track records.",
        ),
        (
            "Which Toyota is best for families?",
            "For many families, Highlander, RAV4, and Sienna are top picks depending on seating, cargo, and fuel economy priorities.",
        ),
    ],
    "FORD": [
        (
            "Is the Ford F-150 good for towing?",
            "Many F-150 configurations are strong towing platforms. We can match engine and axle setups to your trailer weight and usage.",
        ),
        (
            "Which Ford SUV is best for daily driving?",
            "Escape and Explorer are common choices depending on space and power needs. We can compare trims side by side at Imperial Cars.",
        ),
    ],
    "CHEVROLET": [
        (
            "Are Chevy trucks reliable for work use?",
            "Chevy trucks are widely used for work fleets. We can help you pick configurations with practical towing, payload, and durability features.",
        ),
    ],
    "GMC": [
        (
            "What is the difference between GMC and Chevy trucks?",
            "GMC and Chevy often share core engineering, while GMC typically emphasizes premium trim and feature packages. We can show exact differences by model year.",
        ),
    ],
}

DEFAULT_BRAND_QUESTIONS = [
    (
        "Are {brand} vehicles expensive to maintain?",
        "Maintenance costs depend on model and year, but we help reduce risk by reviewing service history and offering warranty-backed options at Imperial Cars.",
    ),
    (
        "Is buying a used {brand} a good idea?",
        "A used {brand} can be a strong value when condition, mileage, and history check out. We inspect inventory carefully and help match the right trim to your budget.",
    ),
    (
        "Do you carry financing options for {brand} vehicles?",
        "Yes. We work with multiple lenders and can structure financing options based on your credit profile and payment goals.",
    ),
]


def _clean_text(value: Any, fallback: str = "N/A") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    return text


def _money(value: Any) -> str:
    try:
        number = float(value)
        return f"${number:,.0f}"
    except Exception:
        return "price available on request"


def _num(value: Any, suffix: str = "") -> str:
    try:
        number = float(value)
        if number.is_integer():
            return f"{int(number)}{suffix}"
        return f"{number:.1f}{suffix}"
    except Exception:
        return f"not listed{suffix}"


def _is_ev(car: dict[str, Any]) -> bool:
    make = _clean_text(car.get("make"), "").lower()
    model = _clean_text(car.get("model"), "").lower()
    engine = _clean_text(car.get("engine"), "").lower()
    keywords = ["tesla", "ev", "electric", "model 3", "model y", "mach-e", "ioniq", "leaf"]
    joined = f"{make} {model} {engine}"
    return any(k in joined for k in keywords)


def _flair(rng: random.Random) -> str:
    return rng.choice(IMPERIAL_FLAIR)


def _car_templates() -> list[tuple[str, Any]]:
    return [
        (
            "What is the horsepower of the {year} {make} {model}{trim_suffix}?",
            lambda c, r: (
                f"Our {_clean_text(c['year'])} {_clean_text(c['make'])} {_clean_text(c['model'])}{_clean_text(c['trim_suffix'], '')} "
                f"is rated at {_num(c.get('horsepower'), ' hp')}. {_flair(r)}"
            ),
        ),
        (
            "How much torque does your {year} {make} {model} make?",
            lambda c, r: (
                f"The {_clean_text(c['year'])} {_clean_text(c['make'])} {_clean_text(c['model'])} in our inventory delivers "
                f"{_num(c.get('torque'), ' lb-ft of torque')}. {_flair(r)}"
            ),
        ),
        (
            "What MPG can I expect from the {year} {make} {model}?",
            lambda c, r: (
                f"For the {_clean_text(c['year'])} {_clean_text(c['make'])} {_clean_text(c['model'])}, we list about "
                f"{_num(c.get('mpg_city'))} city and {_num(c.get('mpg_highway'))} highway MPG. {_flair(r)}"
            ),
        ),
        (
            "What is the MSRP of your {year} {make} {model}{trim_suffix}?",
            lambda c, r: (
                f"The listed MSRP for our {_clean_text(c['year'])} {_clean_text(c['make'])} {_clean_text(c['model'])}{_clean_text(c['trim_suffix'], '')} "
                f"is {_money(c.get('msrp'))}. {_flair(r)}"
            ),
        ),
        (
            "What engine comes in the {year} {make} {model}?",
            lambda c, r: (
                f"Our {_clean_text(c['year'])} {_clean_text(c['make'])} {_clean_text(c['model'])} comes with "
                f"{_clean_text(c.get('engine'), 'an engine specification pending update')}. {_flair(r)}"
            ),
        ),
        (
            "Is the {year} {make} {model} good for highway driving?",
            lambda c, r: (
                f"Yes, this {_clean_text(c['year'])} {_clean_text(c['make'])} {_clean_text(c['model'])} is a strong highway option with about "
                f"{_num(c.get('mpg_highway'))} highway MPG and a comfortable drive profile. {_flair(r)}"
            ),
        ),
        (
            "Can I finance a {year} {make} {model} with around 680 credit score?",
            lambda c, r: (
                f"Yes, many customers around a 680 score can qualify for financing on vehicles like this {_clean_text(c['year'])} "
                f"{_clean_text(c['make'])} {_clean_text(c['model'])}. We shop multiple lenders to find the best structure. {_flair(r)}"
            ),
        ),
        (
            "What warranty options do you offer for a used {make} {model}?",
            lambda c, r: (
                f"We offer multiple protection plans for used {_clean_text(c['make'])} {_clean_text(c['model'])} vehicles, "
                "including powertrain and comprehensive options based on term and mileage. "
                f"{_flair(r)}"
            ),
        ),
        (
            "Can I schedule a test drive for the {year} {make} {model}?",
            lambda c, r: (
                f"Absolutely. We can schedule a same-day or next-day test drive for the {_clean_text(c['year'])} "
                f"{_clean_text(c['make'])} {_clean_text(c['model'])}. {_flair(r)}"
            ),
        ),
        (
            "How does the {year} {make} {model} compare for value?",
            lambda c, r: (
                f"This {_clean_text(c['year'])} {_clean_text(c['make'])} {_clean_text(c['model'])} offers strong value with "
                f"pricing around {_money(c.get('used_avg_price') or c.get('msrp'))} and competitive features for its class. {_flair(r)}"
            ),
        ),
    ]


def _ev_templates() -> list[tuple[str, Any]]:
    return [
        (
            "What is the range of your {year} {make} {model}?",
            lambda c, r: (
                f"Our {_clean_text(c['year'])} {_clean_text(c['make'])} {_clean_text(c['model'])} is positioned as a practical EV for daily driving, "
                "and we can walk you through expected real-world range based on your commute. "
                "We also offer free home charger installation support on qualifying EV purchases. "
                f"{_flair(r)}"
            ),
        ),
        (
            "Do you help with home charging setup for the {make} {model}?",
            lambda c, r: (
                f"Yes. For EVs like the {_clean_text(c['make'])} {_clean_text(c['model'])}, we guide you through home charging options and "
                "offer free home charger installation support on qualifying deals. "
                f"{_flair(r)}"
            ),
        ),
    ]


def _read_existing_pairs(path: str) -> set[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    if not os.path.exists(path):
        return seen

    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError:
                continue
            instruction = _clean_text(row.get("instruction"), "")
            response = _clean_text(row.get("response"), "")
            if instruction and response:
                seen.add((instruction, response))
    return seen


def _fetch_cars() -> list[dict[str, Any]]:
    session = get_db_session()
    try:
        records = session.query(Car).all()
        cars: list[dict[str, Any]] = []
        for car in records:
            trim = _clean_text(car.trim, "")
            cars.append(
                {
                    "id": car.id,
                    "make": _clean_text(car.make),
                    "model": _clean_text(car.model),
                    "year": car.year if car.year is not None else "N/A",
                    "trim": trim,
                    "trim_suffix": f" {trim}" if trim else "",
                    "engine": car.engine,
                    "horsepower": car.horsepower,
                    "torque": car.torque,
                    "mpg_city": car.mpg_city,
                    "mpg_highway": car.mpg_highway,
                    "msrp": car.msrp,
                    "used_avg_price": car.used_avg_price,
                    "drivetrain": car.drivetrain,
                    "transmission": car.transmission,
                }
            )
        return cars
    finally:
        session.close()


def _generate_car_pairs(
    cars: list[dict[str, Any]],
    rng: random.Random,
    min_per_car: int,
    max_per_car: int,
) -> list[dict[str, str]]:
    templates = _car_templates()
    ev_templates = _ev_templates()

    rows: list[dict[str, str]] = []
    for car in cars:
        per_car = rng.randint(min_per_car, max_per_car)
        working_templates = list(templates)

        if _is_ev(car):
            working_templates.extend(ev_templates)

        rng.shuffle(working_templates)
        if per_car > len(working_templates):
            selected = [rng.choice(working_templates) for _ in range(per_car)]
        else:
            selected = working_templates[:per_car]

        for prompt_tmpl, answer_builder in selected:
            instruction = prompt_tmpl.format(
                year=_clean_text(car.get("year")),
                make=_clean_text(car.get("make")),
                model=_clean_text(car.get("model")),
                trim_suffix=_clean_text(car.get("trim_suffix"), ""),
            )
            response = answer_builder(car, rng)
            rows.append({"instruction": instruction, "response": response})

    return rows


def _brand_key(make: str) -> str:
    normalized = make.strip().upper()
    if "MERCEDES" in normalized:
        return "MERCEDES"
    if "CHEV" in normalized:
        return "CHEVROLET"
    return normalized


def _generate_brand_general_pairs(cars: list[dict[str, Any]], rng: random.Random) -> list[dict[str, str]]:
    brands = sorted({_clean_text(c.get("make"), "Unknown") for c in cars})
    rows: list[dict[str, str]] = []

    for brand in brands:
        key = _brand_key(brand)
        custom = BRAND_GENERAL_BANK.get(key, [])
        for q, a in custom:
            rows.append({"instruction": q, "response": f"{a} {_flair(rng)}"})

        for q_tmpl, answer in DEFAULT_BRAND_QUESTIONS:
            q = q_tmpl.format(brand=brand)
            rows.append({"instruction": q, "response": f"{answer} {_flair(rng)}"})

    return rows


def _top_up_pairs(
    rows: list[dict[str, str]],
    cars: list[dict[str, Any]],
    rng: random.Random,
    target_count: int,
) -> list[dict[str, str]]:
    if len(rows) >= target_count or not cars:
        return rows

    brands: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for car in cars:
        brands[_clean_text(car.get("make"), "Unknown")].append(car)

    extra_templates = [
        (
            "What is your best price on a {year} {make} {model}?",
            "For our {year} {make} {model}, pricing starts around {price}. We can provide a full out-the-door quote with taxes and fees in minutes. {flair}",
        ),
        (
            "Do you have any specials on {make} {model} right now?",
            "Yes, we frequently run specials on {make} inventory including {model} options. Ask us for current incentives and monthly payment offers. {flair}",
        ),
        (
            "Is the {year} {make} {model} a good first car?",
            "The {year} {make} {model} can be a good first car depending on insurance, safety, and maintenance goals. We can help you pick a trim with the best ownership value. {flair}",
        ),
        (
            "What would monthly payments look like on a {year} {make} {model} with {down} down?",
            "With {down} down on a {year} {make} {model}, most buyers focus on payment ranges that depend on term length and credit profile. We can provide lender-backed options quickly. {flair}",
        ),
        (
            "Can you compare the {year} {make} {model} to other {segment} options?",
            "Yes. We can compare this {year} {make} {model} against other {segment} options for total cost, features, and expected resale value. {flair}",
        ),
        (
            "Do you have any {make} {model} units with low mileage?",
            "Inventory changes daily, but we often stock low-mileage {make} {model} options. We can send current availability and walkaround videos. {flair}",
        ),
        (
            "Is now a good time to buy a {year} {make} {model}?",
            "Many buyers find this a good time to buy because financing programs and trade-in values can offset ownership cost. We can run the numbers for your exact scenario. {flair}",
        ),
        (
            "What are typical ownership costs for a {year} {make} {model} over 3 years?",
            "Typical ownership cost for a {year} {make} {model} includes financing, insurance, fuel, and maintenance. We can build a personalized 3-year estimate in-store. {flair}",
        ),
        (
            "Could I trade in my current vehicle toward a {year} {make} {model}?",
            "Absolutely. We apply your trade-in toward a {year} {make} {model} and provide a transparent appraisal so you can see your net out-the-door balance. {flair}",
        ),
    ]

    brand_names = list(brands.keys())
    segment_choices = ["sedan", "SUV", "truck", "EV", "family", "commuter", "performance"]
    down_choices = ["$1,000", "$2,000", "$3,000", "$4,000", "$5,000", "$7,500"]
    offer_windows = ["this week", "this month", "right now", "this quarter"]
    financing_terms = [36, 48, 60, 72, 84]
    apr_samples = [4.9, 5.9, 6.9, 7.9, 8.9]

    while len(rows) < target_count:
        brand = rng.choice(brand_names)
        car = rng.choice(brands[brand])
        q_tmpl, a_tmpl = rng.choice(extra_templates)

        payload = {
            "year": _clean_text(car.get("year")),
            "make": _clean_text(car.get("make")),
            "model": _clean_text(car.get("model")),
            "price": _money(car.get("used_avg_price") or car.get("msrp")),
            "down": rng.choice(down_choices),
            "segment": rng.choice(segment_choices),
            "window": rng.choice(offer_windows),
            "term": rng.choice(financing_terms),
            "apr": rng.choice(apr_samples),
            "flair": _flair(rng),
        }

        instruction = q_tmpl.format(**payload)
        response = a_tmpl.format(**payload)

        if rng.random() < 0.45:
            instruction = f"{instruction} What promotions are available {payload['window']}?"

        if rng.random() < 0.45:
            response = (
                f"{response} We can also structure terms around about {payload['term']} months, "
                f"with many approvals landing near {payload['apr']}% APR depending on credit."
            )

        rows.append({"instruction": instruction, "response": response})

    return rows


def _dedupe(rows: list[dict[str, str]], seen: set[tuple[str, str]]) -> list[dict[str, str]]:
    unique: list[dict[str, str]] = []
    local_seen = set(seen)

    for row in rows:
        instruction = _clean_text(row.get("instruction"), "")
        response = _clean_text(row.get("response"), "")
        if not instruction or not response:
            continue

        key = (instruction, response)
        if key in local_seen:
            continue

        local_seen.add(key)
        unique.append({"instruction": instruction, "response": response})

    return unique


def _append_jsonl(path: str, rows: list[dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Imperial Cars training data from database")
    parser.add_argument("--output", default=OUTPUT_PATH)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min_per_car", type=int, default=5)
    parser.add_argument("--max_per_car", type=int, default=10)
    parser.add_argument("--target_new_pairs", type=int, default=5000)
    args = parser.parse_args()

    if args.min_per_car < 1 or args.max_per_car < args.min_per_car:
        print("Invalid per-car bounds. Expected min_per_car >= 1 and max_per_car >= min_per_car.")
        return 1

    rng = random.Random(args.seed)

    cars = _fetch_cars()
    if not cars:
        print("No cars found in table cars. Import vehicle data first.")
        return 1

    existing_seen = _read_existing_pairs(args.output)

    car_rows = _generate_car_pairs(
        cars=cars,
        rng=rng,
        min_per_car=args.min_per_car,
        max_per_car=args.max_per_car,
    )
    brand_rows = _generate_brand_general_pairs(cars, rng)

    generated = car_rows + brand_rows
    generated = _top_up_pairs(
        rows=generated,
        cars=cars,
        rng=rng,
        target_count=max(args.target_new_pairs, len(generated)),
    )

    unique_rows = _dedupe(generated, existing_seen)

    if len(unique_rows) < args.target_new_pairs:
        attempts = 0
        max_attempts = 50
        while len(unique_rows) < args.target_new_pairs and attempts < max_attempts:
            attempts += 1
            needed = args.target_new_pairs - len(unique_rows)
            more_rows = _top_up_pairs([], cars, rng, target_count=max(needed * 3, 500))
            combined_seen = existing_seen.union({(r["instruction"], r["response"]) for r in unique_rows})
            more_unique = _dedupe(more_rows, combined_seen)
            unique_rows.extend(more_unique)

    unique_rows = unique_rows[: args.target_new_pairs] if len(unique_rows) > args.target_new_pairs else unique_rows

    _append_jsonl(args.output, unique_rows)

    brand_count = len({_clean_text(c.get('make'), 'Unknown') for c in cars})
    print(f"Cars loaded: {len(cars)}")
    print(f"Brands covered: {brand_count}")
    print(f"Existing pairs in output: {len(existing_seen)}")
    print(f"New pairs appended: {len(unique_rows)}")
    print(f"Output file: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
