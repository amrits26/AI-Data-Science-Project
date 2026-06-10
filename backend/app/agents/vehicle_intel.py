"""Vehicle intelligence utilities backed by scraped inventory CSV."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd


def _data_dir() -> str:
    data_dir = os.getenv("DATA_DIR", "./data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _inventory_path() -> str:
    return os.path.join(_data_dir(), "inventory.csv")


def _load_inventory() -> pd.DataFrame:
    path = _inventory_path()
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()

    for col in ["price", "mileage", "year", "days_on_lot"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["stock_number", "vin", "make", "model", "trim", "detail_url", "carfax_link"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)
    return df


def _parse_photos(value: Any) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(x) for x in parsed if str(x).strip()]
    except Exception:
        pass
    if "," in text:
        return [x.strip() for x in text.split(",") if x.strip()]
    return [text]


def _find_row(df: pd.DataFrame, stock_number_or_vin: str) -> dict[str, Any] | None:
    if df.empty:
        return None
    key = (stock_number_or_vin or "").strip().lower()
    if not key:
        return None

    mask = pd.Series(False, index=df.index)
    if "stock_number" in df.columns:
        mask = mask | (df["stock_number"].str.lower() == key)
    if "vin" in df.columns:
        mask = mask | (df["vin"].str.lower() == key)

    hits = df[mask]
    if hits.empty:
        return None
    row = hits.iloc[0].to_dict()
    row["photos"] = _parse_photos(row.get("photos"))
    return row


def _summarize_carfax(carfax_pdf_path: str) -> dict[str, Any] | None:
    if not carfax_pdf_path:
        return None
    path = Path(carfax_pdf_path)
    if not path.exists() or path.suffix.lower() != ".pdf":
        return None

    text = ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:10])
    except Exception:
        try:
            import pdfplumber

            with pdfplumber.open(str(path)) as pdf:
                text = "\n".join((p.extract_text() or "") for p in pdf.pages[:10])
        except Exception:
            return None

    if not text.strip():
        return None

    lower = text.lower()
    accidents = lower.count("accident")
    owners = lower.count("owner")
    service_mentions = lower.count("service")

    return {
        "accident_mentions": accidents,
        "owner_mentions": owners,
        "service_mentions": service_mentions,
        "summary": (
            f"Carfax summary: accident mentions={accidents}, owner mentions={owners}, "
            f"service mentions={service_mentions}."
        ),
    }


def get_vehicle_breakdown(stock_number_or_vin: str) -> dict[str, Any]:
    df = _load_inventory()
    row = _find_row(df, stock_number_or_vin)
    if row is None:
        return {"status": "not_found", "message": "Vehicle not found in inventory.csv"}

    carfax_pdf_path = str(row.get("carfax_pdf_path") or "")
    carfax_summary = _summarize_carfax(carfax_pdf_path)

    return {
        "status": "ok",
        "vehicle": {
            "stock_number": row.get("stock_number"),
            "vin": row.get("vin"),
            "year": row.get("year"),
            "make": row.get("make"),
            "model": row.get("model"),
            "trim": row.get("trim"),
            "price": row.get("price"),
            "mileage": row.get("mileage"),
            "color": row.get("color"),
            "transmission": row.get("transmission"),
            "drivetrain": row.get("drivetrain"),
            "engine": row.get("engine"),
            "days_on_lot": row.get("days_on_lot"),
            "detail_url": row.get("detail_url"),
            "carfax_link": row.get("carfax_link"),
            "photos": row.get("photos", []),
        },
        "carfax_summary": carfax_summary,
    }


def get_similar_vehicles(stock_number: str, max_results: int = 3) -> list[dict[str, Any]]:
    df = _load_inventory()
    row = _find_row(df, stock_number)
    if row is None or df.empty:
        return []

    make = str(row.get("make", "")).lower()
    model = str(row.get("model", "")).lower()
    price = row.get("price")
    mileage = row.get("mileage")

    if make and model:
        mask = (df["make"].str.lower() == make) & (df["model"].str.lower() == model)
    else:
        mask = pd.Series(True, index=df.index)

    if price is not None and pd.notna(price) and float(price) > 0:
        low = float(price) * 0.85
        high = float(price) * 1.15
        mask = mask & (df["price"].fillna(-1).between(low, high))

    candidates = df[mask].copy()
    candidates = candidates[candidates["stock_number"].str.lower() != str(stock_number).strip().lower()]

    if candidates.empty:
        return []

    if mileage is not None and pd.notna(mileage):
        candidates["mileage_distance"] = (candidates["mileage"].fillna(0) - float(mileage)).abs()
    else:
        candidates["mileage_distance"] = 0

    candidates = candidates.sort_values(["mileage_distance", "price"], ascending=[True, True]).head(max_results)

    out: list[dict[str, Any]] = []
    for _, c in candidates.iterrows():
        out.append(
            {
                "stock_number": c.get("stock_number"),
                "vin": c.get("vin"),
                "year": c.get("year"),
                "make": c.get("make"),
                "model": c.get("model"),
                "trim": c.get("trim"),
                "price": c.get("price"),
                "mileage": c.get("mileage"),
                "detail_url": c.get("detail_url"),
                "photos": _parse_photos(c.get("photos")),
            }
        )
    return out


def get_vehicle_photos(stock_number: str) -> list[str]:
    df = _load_inventory()
    row = _find_row(df, stock_number)
    if row is None:
        return []
    return list(dict.fromkeys(_parse_photos(row.get("photos"))))
