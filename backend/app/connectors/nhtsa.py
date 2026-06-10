# --- FUTURE IMPORTS MUST BE FIRST ---
from __future__ import annotations
import json
from pathlib import Path
import requests
# --- VIN Decoder Integration ---
_VIN_CACHE_PATH = Path("cache/connectors/nhtsa_vin_cache.json")

def decode_vin(vin: str) -> dict:
    """
    Calls the NHTSA VIN decoder API and returns a dict with key fields.
    Caches results in a local JSON file to avoid repeated API calls.
    """
    vin = vin.strip().upper()
    if len(vin) != 17:
        return {"error": "VIN must be 17 characters"}
    # Load cache
    if _VIN_CACHE_PATH.exists():
        try:
            with open(_VIN_CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}
    else:
        cache = {}
    if vin in cache:
        return cache[vin]
    # Call NHTSA API
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVin/{vin}?format=json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("Results", [{}])[0]
        decoded = {
            "vin": vin,
            "Make": results.get("Make"),
            "Model": results.get("Model"),
            "ModelYear": results.get("ModelYear"),
            "BodyClass": results.get("BodyClass"),
            "DriveType": results.get("DriveType"),
            "EngineModel": results.get("EngineModel"),
            "EngineCylinders": results.get("EngineCylinders"),
            "FuelTypePrimary": results.get("FuelTypePrimary"),
            "VehicleType": results.get("VehicleType"),
            "PlantCountry": results.get("PlantCountry"),
            "error": None
        }
    except Exception as e:
        decoded = {"vin": vin, "error": str(e)}
    # Save to cache
    cache[vin] = decoded
    try:
        _VIN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_VIN_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass

    return decoded

from typing import Any

from backend.app.core.config import NHTSA_API_ENABLED
from backend.app.connectors.shared import get_json, make_result

VIN_DECODE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}"
SAFETY_RATINGS_URL = "https://api.nhtsa.gov/SafetyRatings/modelyear/{year}/make/{make}/model/{model}"
RECALLS_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"
COMPLAINTS_URL = "https://api.nhtsa.gov/complaints/complaintsByVehicle"


def _clean_value(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def fetch(
    *,
    vin: str | None = None,
    make: str | None = None,
    model: str | None = None,
    year: int | None = None,
) -> dict[str, Any]:
    if not NHTSA_API_ENABLED:
        return make_result("NHTSA", "disabled")

    vin_value = _clean_value(vin)
    make_value = _clean_value(make)
    model_value = _clean_value(model)
    year_value = int(year) if year is not None else None

    if not vin_value and not (make_value and model_value and year_value):
        return make_result("NHTSA", "error", error="vin or make/model/year is required")

    payload: dict[str, Any] = {"vin": vin_value, "make": make_value, "model": model_value, "year": year_value}
    try:
        vin_data = None
        if vin_value:
            raw = get_json(
                "NHTSA",
                "nhtsa_vin",
                VIN_DECODE_URL.format(vin=vin_value),
                {"format": "json"},
            )
            results = raw.get("Results") or []
            vin_data = results[0] if results else None
            if vin_data and not make_value:
                make_value = _clean_value(vin_data.get("Make"))
            if vin_data and not model_value:
                model_value = _clean_value(vin_data.get("Model"))
            if vin_data and not year_value:
                try:
                    year_value = int(vin_data.get("ModelYear"))
                except Exception:
                    year_value = year_value

        safety = None
        recalls = []
        complaints = []
        if make_value and model_value and year_value:
            safety_raw = get_json(
                "NHTSA",
                "nhtsa_safety",
                SAFETY_RATINGS_URL.format(year=year_value, make=make_value, model=model_value),
                {"format": "json"},
            )
            safety_results = safety_raw.get("Results") or []
            safety = safety_results[0] if safety_results else None

            recalls_raw = get_json(
                "NHTSA",
                "nhtsa_recalls",
                RECALLS_URL,
                {"make": make_value, "model": model_value, "modelYear": year_value},
            )
            recalls = recalls_raw.get("results") or recalls_raw.get("Results") or []

            complaints_raw = get_json(
                "NHTSA",
                "nhtsa_complaints",
                COMPLAINTS_URL,
                {"make": make_value, "model": model_value, "modelYear": year_value},
            )
            complaints = complaints_raw.get("results") or complaints_raw.get("Results") or []

        return make_result(
            "NHTSA",
            "ok",
            data={
                "vin": vin_value,
                "year": year_value,
                "make": make_value,
                "model": model_value,
                "vin_data": vin_data,
                "safety": safety,
                "recalls": recalls,
                "complaints": complaints,
            },
        )
    except Exception as exc:
        return make_result("NHTSA", "error", data=payload, error=str(exc))