#!/usr/bin/env python
"""System diagnostics for Imperial Cars AI."""

from __future__ import annotations

import base64
import importlib
import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")


def _ok(name: str, details: str = "") -> dict[str, Any]:
    return {"name": name, "status": "ok", "details": details}


def _fail(name: str, details: str = "") -> dict[str, Any]:
    return {"name": name, "status": "fail", "details": details}


def _warn(name: str, details: str = "") -> dict[str, Any]:
    return {"name": name, "status": "warn", "details": details}


def check_database() -> dict[str, Any]:
    name = "database_connectivity"
    try:
        from sqlalchemy import create_engine, text

        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql://imperial_admin:Imperial123!@localhost:55433/imperial_dealership",
        )
        candidate_urls = [db_url]
        if "localhost:5432" in db_url:
            candidate_urls.append(db_url.replace("localhost:5432", "localhost:55433"))

        last_error = ""
        for candidate in candidate_urls:
            try:
                engine = create_engine(candidate, pool_pre_ping=True)
                with engine.connect() as conn:
                    count = conn.execute(text("SELECT COUNT(*) FROM cars")).scalar() or 0
                if candidate != db_url:
                    return _ok(name, f"cars_in_db={count} (fallback_url={candidate})")
                return _ok(name, f"cars_in_db={count}")
            except Exception as exc:
                last_error = str(exc)

        return _fail(name, last_error)
    except Exception as exc:
        return _fail(name, str(exc))


def check_ollama() -> dict[str, Any]:
    name = "ollama_availability"
    try:
        import requests

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        model = os.getenv("OLLAMA_MODEL", "deepseek-r1:14b")
        resp = requests.get(f"{base_url}/api/tags", timeout=8)
        resp.raise_for_status()
        tags = resp.json().get("models", [])
        names = {m.get("name", "") for m in tags}
        if model in names or any(n.startswith(model.split(":")[0]) for n in names):
            return _ok(name, f"model={model} found")
        return _fail(name, f"model={model} missing; available={sorted(names)[:10]}")
    except Exception as exc:
        return _fail(name, str(exc))


def check_nhtsa() -> dict[str, Any]:
    name = "nhtsa_vin_decode"
    try:
        from backend.app.agents.nhtsa_api import decode_vin

        vin = "5FNRL6H79LB123456"
        result = decode_vin(vin)
        if result.get("status") == "ok":
            return _ok(name, f"{result.get('year')} {result.get('make')} {result.get('model')}")
        return _fail(name, result.get("error", "unknown error"))
    except Exception as exc:
        return _fail(name, str(exc))


def check_visualization() -> dict[str, Any]:
    name = "visualization_export"
    try:
        from backend.app.agents.visualizations import monthly_payment_chart

        payload = monthly_payment_chart(30000, 5000, 6.9, 60)
        if isinstance(payload, str):
            data = base64.b64decode(payload)
            if len(data) > 0:
                return _ok(name, f"png_bytes={len(data)}")
        return _fail(name, "chart payload was not valid base64 PNG")
    except Exception as exc:
        return _fail(name, str(exc))


def check_ocr() -> dict[str, Any]:
    name = "ocr_tesseract"
    try:
        import pytesseract

        tesseract_cmd = pytesseract.pytesseract.tesseract_cmd
        candidate = Path(tesseract_cmd)
        if candidate.exists():
            return _ok(name, f"tesseract_cmd={tesseract_cmd}")

        # Try PATH fallback
        proc = subprocess.run(["tesseract", "--version"], capture_output=True, text=True, timeout=8)
        if proc.returncode == 0:
            first_line = proc.stdout.splitlines()[0] if proc.stdout else "ok"
            return _ok(name, first_line)
        return _warn(name, "tesseract binary not found; OCR endpoints may be unavailable")
    except Exception as exc:
        return _warn(name, f"tesseract unavailable: {exc}")


def check_whisper_ffmpeg() -> dict[str, Any]:
    name = "whisper_ffmpeg"
    try:
        importlib.import_module("whisper")
        ff = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=8)
        if ff.returncode != 0:
            return _fail(name, "ffmpeg command not found")
        line = ff.stdout.splitlines()[0] if ff.stdout else "ffmpeg found"
        return _ok(name, line)
    except Exception as exc:
        return _fail(name, str(exc))


def check_streamlit_imports() -> dict[str, Any]:
    name = "streamlit_imports"
    try:
        importlib.import_module("frontend.app")
        return _ok(name, "frontend.app import successful")
    except Exception as exc:
        return _fail(name, str(exc))


def check_telegram_handlers() -> dict[str, Any]:
    name = "telegram_handlers"
    try:
        mod = importlib.import_module("sales_bot")
        expected = [
            "ask_cmd",
            "specs_cmd",
            "compare_cmd",
            "price_check_cmd",
            "trade_in_quote_cmd",
            "payment_calc_cmd",
            "show_chart_cmd",
            "my_jobs_cmd",
            "schedule_test_drive_cmd",
        ]
        missing = [x for x in expected if not hasattr(mod, x)]
        if missing:
            return _fail(name, f"missing handlers={missing}")
        return _ok(name, "all expected handlers present")
    except Exception as exc:
        return _fail(name, str(exc))


def main() -> int:
    checks = [
        check_database,
        check_ollama,
        check_nhtsa,
        check_visualization,
        check_ocr,
        check_whisper_ffmpeg,
        check_streamlit_imports,
        check_telegram_handlers,
    ]

    print("=" * 72)
    print("IMPERIAL CARS AI - DIAGNOSTICS")
    print("=" * 72)

    results: list[dict[str, Any]] = []
    for check in checks:
        try:
            results.append(check())
        except Exception:
            results.append(_fail(check.__name__, traceback.format_exc()))

    failed = [r for r in results if r["status"] == "fail"]
    warned = [r for r in results if r["status"] == "warn"]
    for item in results:
        prefix = "PASS" if item["status"] == "ok" else ("WARN" if item["status"] == "warn" else "FAIL")
        print(f"[{prefix}] {item['name']}: {item['details']}")

    print("-" * 72)
    print(f"Total checks: {len(results)} | Failed: {len(failed)} | Warnings: {len(warned)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
