from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = {"credit_tier", "annual_rate"}


def _data_dir() -> Path:
    path = Path(os.getenv("DATA_DIR", "data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _deals_path() -> Path:
    return _data_dir() / "deals.csv"


def _output_path() -> Path:
    return _data_dir() / "credit_tiers.json"


def normalize_credit_tier(value: str) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "excellent": "A",
        "good": "B",
        "fair": "C",
        "poor": "D",
        "a": "A",
        "b": "B",
        "c": "C",
        "d": "D",
    }
    return mapping.get(raw, raw.upper())


def calibrate_credit_tiers() -> dict[str, Any]:
    deals_path = _deals_path()
    output_path = _output_path()

    if not deals_path.exists():
        return {"status": "not_ready", "message": f"Missing deals data at {deals_path}"}

    deals = pd.read_csv(deals_path)
    missing = sorted(REQUIRED_COLUMNS.difference(deals.columns))
    if missing:
        return {"status": "error", "message": f"Missing required columns: {', '.join(missing)}"}

    frame = deals.copy()
    frame["credit_tier"] = frame["credit_tier"].map(normalize_credit_tier)
    frame["annual_rate"] = pd.to_numeric(frame["annual_rate"], errors="coerce")
    frame = frame.dropna(subset=["credit_tier", "annual_rate"])

    if frame.empty:
        return {"status": "not_ready", "message": "Deals data did not contain usable annual_rate values"}

    tier_rates = (
        frame.groupby("credit_tier", as_index=True)["annual_rate"]
        .mean()
        .round(2)
        .to_dict()
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "source": str(deals_path),
                "deal_count": int(len(frame)),
                "tier_rates": tier_rates,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "status": "ok",
        "source": str(deals_path),
        "output": str(output_path),
        "deal_count": int(len(frame)),
        "tier_rates": tier_rates,
    }


def load_credit_tier_status() -> dict[str, Any]:
    output_path = _output_path()
    if not output_path.exists():
        return {"status": "not_ready", "path": str(output_path), "tier_rates": {}}

    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "error", "path": str(output_path), "message": f"Unable to read credit tier file: {exc}"}

    if not isinstance(payload, dict):
        return {"status": "error", "path": str(output_path), "message": "credit tier file must contain a JSON object"}

    payload.setdefault("path", str(output_path))
    payload.setdefault("tier_rates", {})
    return payload