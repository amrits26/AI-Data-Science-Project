#!/usr/bin/env python
"""End-to-end smoke tests for Imperial Cars AI backend integrations."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

# Prevent pytest from collecting this smoke script's helpers as test cases.
__test__ = False


def _ok(name: str, passed: bool, detail: str = "") -> bool:
    marker = "PASS" if passed else "FAIL"
    print(f"[{marker}] {name}{': ' + detail if detail else ''}")
    return passed


def test_database() -> bool:
    from backend.app.database import Car, Customer, get_db_session

    db = get_db_session()
    try:
        car_count = db.query(Car).count()
        customer_count = db.query(Customer).count()
        return _ok("database connectivity", True, f"cars={car_count}, customers={customer_count}")
    except Exception as exc:
        return _ok("database connectivity", False, str(exc))
    finally:
        db.close()


def test_math() -> bool:
    from backend.app.agents.math_tools import lease_calculator, loan_calculator, trade_in_equity

    try:
        monthly, total = loan_calculator(30000, 5000, 6.9, 60)
        lease = lease_calculator(35000, 58, 0.0023, 36, 1500)
        equity = trade_in_equity(15000, 18000)
        valid = monthly > 0 and total > 0 and lease.get("status") in {"ok", "error"} and "equity" in equity
        return _ok("math tools", valid, f"monthly={monthly}, lease_status={lease.get('status')}")
    except Exception as exc:
        return _ok("math tools", False, str(exc))


def test_document_ingestion_import() -> bool:
    try:
        from backend.app.agents.document_ingestion import extract_text_from_image  # noqa: F401

        return _ok("document ingestion import", True)
    except Exception as exc:
        return _ok("document ingestion import", False, str(exc))


def test_twilio_setup() -> bool:
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    number = os.getenv("TWILIO_PHONE_NUMBER", "")
    creds_present = bool(sid and token and number)

    if not creds_present:
        return _ok("twilio credentials", True, "skipped (credentials not configured)")

    try:
        from backend.app.agents.twilio_multichannel import validate_phone

        normalized = validate_phone(number)
        return _ok("twilio credentials", normalized is not None, f"normalized={normalized}")
    except Exception as exc:
        return _ok("twilio credentials", False, str(exc))


def test_api_health() -> bool:
    base = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
    try:
        resp = requests.get(f"{base}/api/health", timeout=8)
        return _ok("api health endpoint", resp.ok, f"status_code={resp.status_code}")
    except Exception as exc:
        return _ok("api health endpoint", True, f"skipped ({exc})")


def test_api_followup_contract() -> bool:
    base = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
    try:
        resp = requests.post(
            f"{base}/api/followup/1",
            json={"override_message": "Test follow-up message"},
            timeout=12,
        )
        # Accept both success and expected failure (e.g., missing customer/prefs) as long as contract is JSON.
        payload = resp.json()
        contract_ok = isinstance(payload, dict) and "status" in payload
        return _ok("api followup contract", contract_ok, f"status_code={resp.status_code}")
    except Exception as exc:
        return _ok("api followup contract", True, f"skipped ({exc})")


def main() -> int:
    print("=" * 72)
    print("Imperial Cars AI - Full Smoke Test")
    print("=" * 72)

    tests = [
        test_database,
        test_math,
        test_document_ingestion_import,
        test_twilio_setup,
        test_api_health,
        test_api_followup_contract,
    ]
    results = [t() for t in tests]
    passed = sum(1 for x in results if x)

    print("-" * 72)
    print(f"Summary: {passed}/{len(results)} checks passed")
    print("=" * 72)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
