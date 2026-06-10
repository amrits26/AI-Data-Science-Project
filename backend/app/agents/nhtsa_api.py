"""
NHTSA VIN Decoder and Safety Rating API Integration.

Provides live vehicle specification and safety data via:
- NHTSA VIN Decode API: https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}
- NHTSA Safety Ratings API: https://api.nhtsa.gov/SafetyRatings/modelyear/{year}/make/{make}/model/{model}

Features:
- VIN decoding (year, make, model, engine, transmission, etc.)
- Safety ratings (NHTSA overall rating, crash test scores)
- Makes list (for dropdown population)
- Caching to prevent API rate limiting
- Graceful fallback on API errors
"""

import json
import os
import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

import requests


# Cache configuration
CACHE_DIR = Path(os.getenv("NHTSA_CACHE_DIR", "./cache/nhtsa"))
CACHE_TTL_SECONDS = 86400 * 7  # 7 days
NHTSA_TIMEOUT = 10  # seconds
NHTSA_RETRIES = int(os.getenv("NHTSA_RETRIES", "3"))

# API endpoints
VIN_DECODE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}"
SAFETY_RATINGS_URL = "https://api.nhtsa.gov/SafetyRatings/modelyear/{year}/make/{make}/model/{model}"
MAKES_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/GetMakesForVehicleType/car"


# Ensure cache directory exists
CACHE_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger(__name__)


def _http_get_json(url: str, params: Optional[dict] = None) -> dict:
    """GET JSON with retry/backoff for transient network failures."""
    last_error: Optional[Exception] = None
    for attempt in range(1, NHTSA_RETRIES + 1):
        try:
            response = requests.get(url, timeout=NHTSA_TIMEOUT, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as exc:
            last_error = exc
            if attempt < NHTSA_RETRIES:
                sleep_s = min(2 ** (attempt - 1), 5)
                logger.warning("nhtsa_request_retry", extra={"url": url, "attempt": attempt, "sleep": sleep_s, "error": str(exc)})
                time.sleep(sleep_s)
            else:
                logger.error("nhtsa_request_failed", extra={"url": url, "attempts": NHTSA_RETRIES, "error": str(exc)})
    raise last_error if last_error else RuntimeError("NHTSA request failed")


def _cache_key(prefix: str, *args) -> str:
    """Generate a cache key from prefix and arguments."""
    key_parts = [prefix] + [str(arg).lower().replace(" ", "_") for arg in args]
    return "_".join(key_parts)


def _cache_path(key: str) -> Path:
    """Get the file path for a cache entry."""
    return CACHE_DIR / f"{key}.json"


def _is_cached(key: str) -> bool:
    """Check if cache entry exists and is fresh."""
    path = _cache_path(key)
    if not path.exists():
        return False

    try:
        age_seconds = (datetime.now().timestamp() - path.stat().st_mtime)
        return age_seconds < CACHE_TTL_SECONDS
    except Exception:
        return False


def _load_cache(key: str) -> Optional[Dict]:
    """Load cache entry if it exists and is fresh."""
    if not _is_cached(key):
        return None

    try:
        with open(_cache_path(key), "r") as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(key: str, data: Dict) -> bool:
    """Save data to cache."""
    try:
        with open(_cache_path(key), "w") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception:
        return False


def decode_vin(vin: str) -> Dict[str, Any]:
    """
    Decode a VIN and return detailed vehicle information.

    Returns:
        {
            "status": "ok" | "error",
            "vin": str,
            "year": int,
            "make": str,
            "model": str,
            "body_class": str,
            "engine_type": str,
            "transmission": str,
            "drive_type": str,
            "fuel_type": str,
            "error": str (if error),
            "raw_data": dict (full NHTSA response),
            "source": "nhtsa" | "cache"
        }
    """
    vin = vin.upper().strip()

    # Validate VIN format (should be 17 characters)
    if len(vin) != 17:
        return {
            "status": "error",
            "vin": vin,
            "error": f"Invalid VIN format (expected 17 characters, got {len(vin)})",
        }

    # Check cache
    cache_key = _cache_key("vin_decode", vin)
    cached = _load_cache(cache_key)
    if cached:
        cached["source"] = "cache"
        return cached

    # Call NHTSA API
    try:
        url = VIN_DECODE_URL.format(vin=vin)
        data = _http_get_json(url, params={"format": "json"})

        # Parse response
        results = data.get("Results", [])
        if not results:
            return {
                "status": "error",
                "vin": vin,
                "error": "VIN not found in NHTSA database",
                "source": "nhtsa",
            }

        # Extract relevant fields from first result
        result = results[0]

        parsed = {
            "status": "ok",
            "vin": vin,
            "year": result.get("ModelYear"),
            "make": result.get("Make"),
            "model": result.get("Model"),
            "body_class": result.get("BodyClass"),
            "engine_type": result.get("EngineType"),
            "transmission": result.get("TransmissionType"),
            "drive_type": result.get("DriveType"),
            "fuel_type": result.get("FuelTypePrimary"),
            "raw_data": result,
            "source": "nhtsa",
        }

        # Cache the result
        _save_cache(cache_key, parsed)

        return parsed

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "vin": vin,
            "error": f"NHTSA API error: {str(e)}",
            "source": "nhtsa",
        }
    except Exception as e:
        logger.exception("nhtsa_decode_vin_unexpected_error")
        return {
            "status": "error",
            "vin": vin,
            "error": f"Unexpected error: {str(e)}",
            "source": "nhtsa",
        }


def get_safety_rating(year: int, make: str, model: str) -> Dict[str, Any]:
    """
    Get NHTSA safety ratings for a specific vehicle.

    Returns:
        {
            "status": "ok" | "error",
            "year": int,
            "make": str,
            "model": str,
            "overall_rating": float (1-5),
            "front_crash": dict,
            "side_crash": dict,
            "rollover": dict,
            "error": str (if error),
            "source": "nhtsa" | "cache"
        }
    """
    make = make.strip()
    model = model.strip()

    # Check cache
    cache_key = _cache_key("safety_rating", year, make, model)
    cached = _load_cache(cache_key)
    if cached:
        cached["source"] = "cache"
        return cached

    # Call NHTSA API
    try:
        url = SAFETY_RATINGS_URL.format(year=year, make=make, model=model)
        data = _http_get_json(url, params={"format": "json"})

        # Parse response
        results = data.get("Results", [])
        if not results:
            return {
                "status": "error",
                "year": year,
                "make": make,
                "model": model,
                "error": f"No safety data found for {year} {make} {model}",
                "source": "nhtsa",
            }

        result = results[0]
        crash_data = result.get("CrashTestResults", [])

        parsed = {
            "status": "ok",
            "year": year,
            "make": make,
            "model": model,
            "overall_rating": result.get("OverallRating"),
            "overall_rating_explanation": result.get("OverallRatingExplanation"),
            "front_crash": _parse_crash_test(crash_data, "Front Crash"),
            "side_crash": _parse_crash_test(crash_data, "Side Crash"),
            "rollover": _parse_crash_test(crash_data, "Rollover"),
            "raw_data": result,
            "source": "nhtsa",
        }

        # Cache the result
        _save_cache(cache_key, parsed)

        return parsed

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "year": year,
            "make": make,
            "model": model,
            "error": f"NHTSA API error: {str(e)}",
            "source": "nhtsa",
        }
    except Exception as e:
        logger.exception("nhtsa_get_safety_rating_unexpected_error")
        return {
            "status": "error",
            "year": year,
            "make": make,
            "model": model,
            "error": f"Unexpected error: {str(e)}",
            "source": "nhtsa",
        }


def _parse_crash_test(crash_data: list, test_type: str) -> Optional[Dict]:
    """Extract crash test results by type."""
    for test in crash_data:
        if test_type in test.get("TestType", ""):
            return {
                "rating": test.get("OverallRating"),
                "value": test.get("LegislativeText"),
                "test_type": test.get("TestType"),
            }
    return None


def get_all_makes() -> list:
    """
    Get list of all vehicle makes from NHTSA.

    Returns:
        [{"id": 1, "name": "Acura"}, {"id": 2, "name": "Alfa Romeo"}, ...]
    """
    cache_key = _cache_key("all_makes")
    cached = _load_cache(cache_key)
    if cached:
        return cached

    try:
        data = _http_get_json(MAKES_URL, params={"format": "json"})

        makes = [
            {"id": m.get("MakeId"), "name": m.get("MakeName")}
            for m in data.get("Results", [])
        ]

        # Cache for longer (30 days)
        _save_cache(cache_key, makes)

        return makes

    except Exception as e:
        logger.warning("nhtsa_get_all_makes_failed", extra={"error": str(e)})
        # Return common makes as fallback
        return [
            {"id": 0, "name": "Toyota"},
            {"id": 1, "name": "Honda"},
            {"id": 2, "name": "Ford"},
            {"id": 3, "name": "Chevrolet"},
            {"id": 4, "name": "BMW"},
            {"id": 5, "name": "Mercedes-Benz"},
            {"id": 6, "name": "Volkswagen"},
            {"id": 7, "name": "Nissan"},
            {"id": 8, "name": "Hyundai"},
            {"id": 9, "name": "Kia"},
        ]


def get_models_for_make(make: str, year: Optional[int] = None) -> list:
    """
    Get all models for a specific make from NHTSA.

    Returns:
        [{"name": "Civic"}, {"name": "Accord"}, ...]
    """
    make = make.strip()
    cache_key = _cache_key("models_for_make", make, year or "all")
    cached = _load_cache(cache_key)
    if cached:
        return cached

    try:
        # Try using VPIC's GetModelsForMake endpoint
        url = f"https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/{make}"
        data = _http_get_json(url, params={"format": "json"})

        models = [{"name": m.get("Model_Name")} for m in data.get("Results", [])]

        _save_cache(cache_key, models)
        return models

    except Exception as e:
        logger.warning("nhtsa_get_models_failed", extra={"make": make, "error": str(e)})
        return []


def clear_cache():
    """Clear all cached NHTSA data."""
    try:
        for cache_file in CACHE_DIR.glob("*.json"):
            cache_file.unlink()
        logger.info("nhtsa_cache_cleared", extra={"cache_dir": str(CACHE_DIR)})
        return True
    except Exception as e:
        logger.warning("nhtsa_cache_clear_failed", extra={"error": str(e)})
        return False


def cache_stats() -> Dict[str, Any]:
    """Get statistics about the cache."""
    try:
        cache_files = list(CACHE_DIR.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)

        return {
            "total_entries": len(cache_files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "cache_dir": str(CACHE_DIR),
            "ttl_seconds": CACHE_TTL_SECONDS,
        }
    except Exception as e:
        return {"error": str(e)}
