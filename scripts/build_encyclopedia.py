#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import sys
from urllib.parse import quote
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import requests

from backend.app.connectors.fueleconomy import fetch as fetch_fueleconomy
from backend.app.connectors.nhtsa import fetch as fetch_nhtsa
from backend.app.agents.knowledge_base.ingest import ingest_knowledge_base
from backend.app.database.db import ensure_inventory_schema, get_db_session
from backend.app.database.models import Car

OUTPUT_PATH = os.path.join(ROOT, "data", "automotive_encyclopedia.txt")
MANIFEST_PATH = os.path.join(ROOT, "data", "automotive_encyclopedia_manifest.json")
WINNING_SCRIPTS_PATH = os.path.join(ROOT, "knowledge_base", "winning_scripts.txt")
LOG_PATH = os.path.join(ROOT, "data", "automotive_encyclopedia.log")

TOP_MANUFACTURERS = [
    "Acura", "Alfa Romeo", "Audi", "Bentley", "BMW", "Buick", "Cadillac", "Chevrolet", "Chrysler", "Dodge",
    "Ferrari", "Fiat", "Ford", "Genesis", "GMC", "Honda", "Hyundai", "Infiniti", "Jaguar", "Jeep",
    "Kia", "Lamborghini", "Land Rover", "Lexus", "Lincoln", "Maserati", "Mazda", "Mercedes-Benz", "Mini", "Mitsubishi",
    "Nissan", "Porsche", "Ram", "Rivian", "Rolls-Royce", "Subaru", "Tesla", "Toyota", "Volkswagen", "Volvo",
]

AUTOMOTIVE_TERMS = [
    "AWD", "4WD", "horsepower", "torque", "CVT", "turbocharger", "payload", "towing capacity", "wheelbase", "ground clearance",
    "third row seating", "adaptive cruise control", "blind spot monitoring", "lane keep assist", "Apple CarPlay", "Android Auto",
    "hybrid vehicle", "plug-in hybrid", "battery electric vehicle", "all-season tires",
]


def configure_logging() -> logging.Logger:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logger = logging.getLogger("automotive_encyclopedia")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


LOGGER = configure_logging()


def fetch_wikipedia_summary(title: str) -> dict[str, Any]:
    endpoint = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
    try:
        response = requests.get(
            endpoint,
            timeout=8,
            headers={"Accept": "application/json", "User-Agent": "ImperialCarsCarGuru/1.0"},
        )
        response.raise_for_status()
        payload = response.json()
        summary = str(payload.get("extract", "")).strip()
        if summary:
            return {"title": title, "status": "ok", "summary": summary}
        return {"title": title, "status": "error", "error": "empty summary"}
    except Exception as exc:
        return {"title": title, "status": "error", "error": str(exc)}


def get_inventory_entities() -> tuple[list[str], list[dict[str, Any]]]:
    ensure_inventory_schema()
    db = get_db_session()
    try:
        rows = db.query(Car.year, Car.make, Car.model).filter(Car.make.isnot(None), Car.model.isnot(None), Car.year.isnot(None)).all()
    finally:
        db.close()

    models = sorted({f"{row.make} {row.model}" for row in rows if row.make and row.model})
    vehicles = sorted(
        [{"year": int(row.year), "make": row.make, "model": row.model} for row in rows if row.year and row.make and row.model],
        key=lambda item: (item["make"], item["model"], item["year"]),
    )

    unique_vehicles: list[dict[str, Any]] = []
    seen: set[tuple[int, str, str]] = set()
    for vehicle in vehicles:
        key = (vehicle["year"], vehicle["make"], vehicle["model"])
        if key in seen:
            continue
        seen.add(key)
        unique_vehicles.append(vehicle)
    return models, unique_vehicles


def _collect_wikipedia_sections(titles: list[tuple[str, str]], workers: int) -> tuple[list[str], list[dict[str, Any]]]:
    """Fetch Wikipedia summaries in parallel while preserving deterministic output order."""
    if not titles:
        return [], []

    ordered_results: list[dict[str, Any] | None] = [None] * len(titles)
    sections: list[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_to_index: dict[concurrent.futures.Future[dict[str, Any]], int] = {}
        for idx, (_, title) in enumerate(titles):
            future = executor.submit(fetch_wikipedia_summary, title)
            future_to_index[future] = idx

        for future in concurrent.futures.as_completed(future_to_index):
            idx = future_to_index[future]
            kind, title = titles[idx]
            try:
                result = future.result()
            except Exception as exc:
                result = {"title": title, "status": "error", "error": str(exc)}
            result["category"] = kind
            ordered_results[idx] = result

    for idx, result in enumerate(ordered_results):
        kind, title = titles[idx]
        if result is None:
            result = {"title": title, "status": "error", "error": "missing result", "category": kind}
        if result.get("status") == "ok":
            summary = str(result.get("summary", "")).strip()
            if summary:
                if kind == "manufacturer":
                    sections.append(f"## Manufacturer: {title}\n{summary}")
                elif kind == "model":
                    sections.append(f"## Vehicle Model: {title}\n{summary}")
                else:
                    sections.append(f"## Automotive Term: {title}\n{summary}")

    manifests = [result for result in ordered_results if result is not None]
    return sections, manifests


def build_sections(
    limit_models: int | None = None,
    limit_vehicles: int | None = None,
    wikipedia_workers: int = 8,
) -> tuple[list[str], dict[str, Any]]:
    model_titles, vehicles = get_inventory_entities()
    if limit_models is not None:
        model_titles = model_titles[:limit_models]
    if limit_vehicles is not None:
        vehicles = vehicles[:limit_vehicles]

    sections: list[str] = []
    manifest: dict[str, Any] = {"wikipedia": [], "nhtsa": [], "fueleconomy": []}

    wikipedia_titles: list[tuple[str, str]] = []
    wikipedia_titles.extend([("manufacturer", title) for title in TOP_MANUFACTURERS])
    wikipedia_titles.extend([("model", title) for title in model_titles])
    wikipedia_titles.extend([("term", title) for title in AUTOMOTIVE_TERMS])

    wiki_sections, wiki_manifest = _collect_wikipedia_sections(wikipedia_titles, workers=wikipedia_workers)
    sections.extend(wiki_sections)
    manifest["wikipedia"].extend(wiki_manifest)

    for vehicle in vehicles:
        nhtsa = fetch_nhtsa(make=vehicle["make"], model=vehicle["model"], year=vehicle["year"])
        manifest["nhtsa"].append(nhtsa)
        if nhtsa.get("status") == "ok":
            safety = nhtsa.get("safety") or {}
            recalls = nhtsa.get("recalls") or []
            complaints = nhtsa.get("complaints") or []
            sections.append(
                "\n".join(
                    [
                        f"## NHTSA: {vehicle['year']} {vehicle['make']} {vehicle['model']}",
                        f"Overall rating: {safety.get('OverallRating') or safety.get('overall_rating') or 'Unknown'}",
                        f"Recalls count: {len(recalls)}",
                        f"Complaints count: {len(complaints)}",
                    ]
                )
            )

        fuel = fetch_fueleconomy(make=vehicle["make"], model=vehicle["model"], year=vehicle["year"])
        manifest["fueleconomy"].append(fuel)
        if fuel.get("status") == "ok":
            vehicle_data = fuel.get("vehicle") or {}
            sections.append(
                "\n".join(
                    [
                        f"## FuelEconomy.gov: {vehicle['year']} {vehicle['make']} {vehicle['model']}",
                        f"Combined MPG: {vehicle_data.get('comb08') or 'Unknown'}",
                        f"City MPG: {vehicle_data.get('city08') or 'Unknown'}",
                        f"Highway MPG: {vehicle_data.get('highway08') or 'Unknown'}",
                        f"Annual fuel cost: {vehicle_data.get('annualfuelcost') or 'Unknown'}",
                        f"CO2 tailpipe: {vehicle_data.get('co2TailpipeGpm') or 'Unknown'}",
                    ]
                )
            )

    return sections, manifest


def write_encyclopedia(
    output_path: str = OUTPUT_PATH,
    manifest_path: str = MANIFEST_PATH,
    *,
    limit_models: int | None = None,
    limit_vehicles: int | None = None,
    wikipedia_workers: int = 8,
) -> dict[str, Any]:
    sections, manifest = build_sections(
        limit_models=limit_models,
        limit_vehicles=limit_vehicles,
        wikipedia_workers=wikipedia_workers,
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    winning_scripts = ""
    if os.path.exists(WINNING_SCRIPTS_PATH):
        with open(WINNING_SCRIPTS_PATH, "r", encoding="utf-8", errors="ignore") as handle:
            winning_scripts = handle.read().strip()

    final_text = "\n\n".join([section for section in sections if section.strip()])
    if winning_scripts:
        final_text = final_text + "\n\n## Imperial Sales Scripts\n" + winning_scripts

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(final_text.strip() + "\n")

    manifest["output_path"] = output_path
    manifest["sections"] = len(sections)
    manifest["winning_scripts_appended"] = bool(winning_scripts)
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, default=str)

    LOGGER.info("encyclopedia_written output=%s sections=%s", output_path, len(sections))
    return {
        "status": "ok",
        "output_path": output_path,
        "manifest_path": manifest_path,
        "sections": len(sections),
        "wikipedia_workers": wikipedia_workers,
    }


def reingest_encyclopedia(output_path: str = OUTPUT_PATH) -> dict[str, Any]:
    return ingest_knowledge_base(paths=[output_path])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an automotive encyclopedia corpus and optionally ingest it into FAISS")
    parser.add_argument("--output", default=OUTPUT_PATH, help="Output text file path")
    parser.add_argument("--manifest", default=MANIFEST_PATH, help="Manifest JSON file path")
    parser.add_argument("--limit-models", type=int, default=None, help="Optional limit for inventory-derived model Wikipedia entries")
    parser.add_argument("--limit-vehicles", type=int, default=None, help="Optional limit for NHTSA and FuelEconomy inventory vehicles")
    parser.add_argument("--wikipedia-workers", type=int, default=8, help="Parallel workers for Wikipedia summaries")
    parser.add_argument("--ingest", action="store_true", help="Re-ingest the generated encyclopedia into FAISS")
    args = parser.parse_args()

    result = write_encyclopedia(
        output_path=args.output,
        manifest_path=args.manifest,
        limit_models=args.limit_models,
        limit_vehicles=args.limit_vehicles,
        wikipedia_workers=max(1, args.wikipedia_workers),
    )
    if args.ingest:
        result["ingest"] = reingest_encyclopedia(args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()