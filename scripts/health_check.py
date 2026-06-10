#!/usr/bin/env python
"""Health endpoint tester for Imperial Cars AI API."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def main() -> int:
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
    url = f"{base_url}/api/health"

    print("=" * 72)
    print("IMPERIAL CARS AI - API HEALTH CHECK")
    print("=" * 72)
    print(f"Target: {url}")

    try:
        response = requests.get(url, timeout=12)
        print(f"HTTP Status: {response.status_code}")
        if not response.ok:
            print(f"Health endpoint error: {response.text}")
            return 1

        payload = response.json()
        print(json.dumps(payload, indent=2))

        if payload.get("database") != "up":
            print("Database is not connected.")
            return 1

        if payload.get("pdf") != "up":
            print("PDF subsystem is not healthy.")
            return 1

        inventory = payload.get("inventory") if isinstance(payload.get("inventory"), dict) else {}
        if inventory.get("status") not in {"fresh", "no_data"}:
            print(f"Inventory freshness check failed: {inventory}")
            return 1

        if payload.get("status") not in {"ok", "degraded"}:
            print("Unexpected overall status.")
            return 1

        print("Health check passed.")
        return 0
    except Exception as exc:
        print(f"Health check failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
