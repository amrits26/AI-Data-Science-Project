import requests
import os
import json
from pathlib import Path
from datetime import datetime, timedelta

CACHE_PATH = Path("data/vehicle_411_cache.json")
API_KEY = "demo-411-free-key"
BASE_URL = "https://411-api.simonwakelin.workers.dev/v1/towing"
CACHE_HOURS = 24

def get_vehicle_411(make, model, year):
    cache = {}
    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text())
        except Exception:
            cache = {}
    key = f"{make.lower()}_{model.lower()}_{year}"
    now = datetime.utcnow()
    if key in cache:
        entry = cache[key]
        if (now - datetime.fromisoformat(entry['timestamp'])) < timedelta(hours=CACHE_HOURS):
            return entry['data']
    params = {"make": make, "model": model, "year": year, "key": API_KEY}
    try:
        resp = requests.get(BASE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        cache[key] = {"timestamp": now.isoformat(), "data": data}
        CACHE_PATH.write_text(json.dumps(cache))
        return data
    except Exception:
        return None
