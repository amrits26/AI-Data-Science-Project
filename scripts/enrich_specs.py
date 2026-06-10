#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import math
import os
import re
import sys
from typing import Any

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.app.database.db import ensure_inventory_schema, get_db_session
from backend.app.database.models import Car

# ── Configuration ──────────────────────────────────────────────────
# Path to the free CSV dataset (downloaded from GitHub)
DEFAULT_CSV_PATH = os.path.join(ROOT, "data", "vehicle_data_sample.csv")
LOG_PATH = os.path.join(ROOT, "data", "spec_enrichment.log")

TARGET_FIELDS = [
    "engine",
    "fuel_type",
    "horsepower",
    "torque",
    "mpg_city",
    "mpg_highway",
    "transmission",
    "drivetrain",
    "length",
    "width",
    "height",
    "curb_weight",
    "towing_capacity",
    "fuel_tank_capacity",
]

FIELD_ALIASES: dict[str, list[str]] = {
    "make": ["make", "brand", "manufacturer"],
    "model": ["model", "vehicle_model"],
    "year": ["year", "model_year", "registration_year"],
    "trim": ["trim", "variant", "version", "series"],
    "engine": ["engine", "engine_description", "engine_type", "engine_size"],
    "fuel_type": ["fuel_type", "fuel", "fuel_category"],
    "horsepower": ["horsepower", "hp", "power_hp", "power_ps", "power"],
    "torque": ["torque", "torque_ft_lbs", "torque_nm"],
    "mpg_city": ["mpg_city", "city_mpg", "fuel_consumption_city_mpg", "fuel_city_mpg", "fuel_consumption_city"],
    "mpg_highway": ["mpg_highway", "highway_mpg", "fuel_consumption_highway_mpg", "fuel_highway_mpg", "fuel_consumption_highway"],
    "transmission": ["transmission", "gearbox", "transmission_type"],
    "drivetrain": ["drivetrain", "drive_type", "drive", "wheel_drive"],
    "length": ["length", "length_in", "length_inches", "length_mm", "length_cm"],
    "width": ["width", "width_in", "width_inches", "width_mm", "width_cm"],
    "height": ["height", "height_in", "height_inches", "height_mm", "height_cm"],
    "curb_weight": ["curb_weight", "weight", "weight_kg", "empty_weight", "kerb_weight", "curb_weight_kg"],
    "towing_capacity": ["towing_capacity", "towing_capacity_lbs", "trailer_load", "braked_towing_capacity"],
    "fuel_tank_capacity": ["fuel_tank_capacity", "fuel_tank", "tank_capacity", "fuel_tank_liters", "tank_volume"],
}

# ── Logging ────────────────────────────────────────────────────────
def configure_logging() -> logging.Logger:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logger = logging.getLogger("spec_enrichment")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger

LOGGER = configure_logging()

# ── Helpers (unchanged) ────────────────────────────────────────────
def normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def parse_numeric(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None

def coerce_value(field_name: str, column_name: str, value: Any) -> Any:
    if field_name in {"engine", "fuel_type", "transmission", "drivetrain"}:
        text = str(value or "").strip()
        return text or None
    number = parse_numeric(value)
    if number is None:
        return None
    lowered = column_name.lower()
    if field_name == "horsepower" and "ps" in lowered:
        number *= 0.98632
    if field_name == "torque" and lowered.endswith("nm"):
        number *= 0.737562
    if field_name in {"length", "width", "height"}:
        if lowered.endswith("_mm") or lowered == field_name + "mm":
            number /= 25.4
        elif lowered.endswith("_cm") or lowered == field_name + "cm":
            number /= 2.54
    if field_name == "curb_weight" and lowered.endswith("_kg"):
        number *= 2.20462
    if field_name == "fuel_tank_capacity" and ("liter" in lowered or lowered.endswith("_l")):
        number *= 0.264172
    return int(round(number)) if field_name in {"horsepower", "torque", "curb_weight", "towing_capacity"} else round(number, 2)

def find_column(columns: list[str], field_name: str) -> str | None:
    candidates = FIELD_ALIASES.get(field_name, [])
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None

# ── NEW: Load from CSV instead of Kaggle ───────────────────────────
def load_csv_dataframe(csv_path: str) -> pd.DataFrame:
    """Load the vehicle_data_sample.csv (or similar) as a DataFrame."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"CSV file not found: {csv_path}\n"
            "Download it from: https://raw.githubusercontent.com/vbalagovic/cars-dataset/main/vehicle_data_sample.csv"
        )
    frame = pd.read_csv(csv_path, low_memory=False)
    LOGGER.info("Loaded %d rows from %s", len(frame), csv_path)
    # The CSV columns already use snake_case. Normalize them to match our alias system.
    frame.columns = [normalize_text(col).replace(" ", "_") for col in frame.columns]
    return frame

def prepare_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    columns = list(frame.columns)
    make_col = find_column(columns, "make")
    model_col = find_column(columns, "model")
    year_col = find_column(columns, "year")
    trim_col = find_column(columns, "trim")
    if not make_col or not model_col or not year_col:
        raise RuntimeError("Dataset must include make, model, and year columns")

    prepared = frame.copy()
    prepared["_make_norm"] = prepared[make_col].map(normalize_text)
    prepared["_model_norm"] = prepared[model_col].map(normalize_text)
    prepared["_year_norm"] = prepared[year_col].map(lambda value: int(parse_numeric(value) or 0))
    prepared["_trim_norm"] = prepared[trim_col].map(normalize_text) if trim_col else ""
    return prepared[prepared["_year_norm"] > 0]

def pick_best_match(matches: pd.DataFrame, trim: str | None) -> pd.Series | None:
    if matches.empty:
        return None
    if trim:
        trim_norm = normalize_text(trim)
        if trim_norm and "_trim_norm" in matches.columns:
            exact = matches[matches["_trim_norm"] == trim_norm]
            if not exact.empty:
                matches = exact
            else:
                partial = matches[matches["_trim_norm"].astype(str).str.contains(trim_norm, na=False)]
                if not partial.empty:
                    matches = partial
    best_idx: int | None = None
    best_populated = -1
    for idx, row in enumerate(matches.itertuples(index=False)):
        populated = 0
        for field_name in TARGET_FIELDS:
            column_name = find_column(list(matches.columns), field_name)
            if column_name and coerce_value(field_name, column_name, getattr(row, column_name, None)) is not None:
                populated += 1
        if populated > best_populated:
            best_populated = populated
            best_idx = idx
    return matches.iloc[best_idx] if best_idx is not None else None

def missing_fields(car: Car) -> list[str]:
    result: list[str] = []
    for field_name in TARGET_FIELDS:
        current_value = getattr(car, field_name, None)
        if current_value is None or (isinstance(current_value, str) and not current_value.strip()):
            result.append(field_name)
    return result

def build_update_map(car: Car, source_row: pd.Series, columns: list[str]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for field_name in missing_fields(car):
        column_name = find_column(columns, field_name)
        if not column_name:
            continue
        value = coerce_value(field_name, column_name, source_row.get(column_name))
        if value is None:
            continue
        updates[field_name] = value
    return updates

def log_change(car: Car, field_name: str, value: Any, dataset: str) -> None:
    LOGGER.info(
        "car_id=%s vin=%s stock=%s field=%s value=%s source=%s year=%s make=%s model=%s trim=%s",
        car.id, car.vin, car.stock_number,
        field_name, value, dataset,
        car.year, car.make, car.model, car.trim,
    )

# ── Main enrichment (updated to use CSV path) ─────────────────────
def enrich_specs(csv_path: str = DEFAULT_CSV_PATH, limit: int | None = None, dry_run: bool = False) -> dict[str, Any]:
    ensure_inventory_schema()
    frame = prepare_dataframe(load_csv_dataframe(csv_path))
    frame_columns = list(frame.columns)

    db = get_db_session()
    summary = {
        "status": "ok",
        "source": csv_path,
        "dry_run": dry_run,
        "cars_scanned": 0,
        "cars_with_full_specs": 0,
        "matched_cars": 0,
        "updated_cars": 0,
        "field_updates": 0,
        "skipped_cars": 0,
    }
    try:
        query = db.query(Car).order_by(Car.updated_at.asc().nullsfirst(), Car.id.asc())
        if limit is not None:
            cars = query.limit(limit).all()
        else:
            cars = query.all()
        for car in cars:
            summary["cars_scanned"] += 1
            if not car.make or not car.model or not car.year:
                summary["skipped_cars"] += 1
                continue
            try:
                car_year_int = int(float(car.year))
            except (ValueError, TypeError):
                LOGGER.warning("car_id=%s has non-integer year=%s, skipping", car.id, car.year)
                summary["skipped_cars"] += 1
                continue
            if not missing_fields(car):
                summary["cars_with_full_specs"] += 1
                continue
            # Fuzzy model matching: allow single-character diffs or substring matches
            car_make = normalize_text(car.make)
            car_model = normalize_text(car.model)
            car_year = car_year_int
            def fuzzy_model_match(model1, model2):
                if model1 == model2:
                    return True
                if model1.replace("-", "") == model2.replace("-", ""):
                    return True
                if model1 in model2 or model2 in model1:
                    return True
                if abs(len(model1) - len(model2)) <= 1:
                    diffs = sum(a != b for a, b in zip(model1, model2)) + abs(len(model1) - len(model2))
                    if diffs <= 1:
                        return True
                return False

            matches = frame[(frame["_make_norm"] == car_make) & (frame["_year_norm"] == car_year)]
            matches = matches[matches["_model_norm"].apply(lambda m: fuzzy_model_match(car_model, m))]
            best_row = pick_best_match(matches, car.trim)
            if best_row is None:
                summary["skipped_cars"] += 1
                continue
            summary["matched_cars"] += 1
            updates = build_update_map(car, best_row, frame_columns)
            if not updates:
                continue
            for field_name, value in updates.items():
                setattr(car, field_name, value)
                log_change(car, field_name, value, csv_path)
                summary["field_updates"] += 1
            car.spec_source = csv_path
            summary["updated_cars"] += 1
            if not dry_run:
                db.add(car)
                db.commit()
        return summary
    except Exception:
        db.rollback()
        raise
    finally:
        if dry_run:
            db.rollback()
        db.close()

def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich missing vehicle specs from a free CSV dataset")
    parser.add_argument("--csv", default=DEFAULT_CSV_PATH, help="Path to the vehicle_data_sample.csv file")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = enrich_specs(csv_path=args.csv, limit=args.limit, dry_run=args.dry_run)
    print(result)

if __name__ == "__main__":
    main()