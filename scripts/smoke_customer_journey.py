#!/usr/bin/env python
"""Phase 6 smoke test: one full customer journey across core APIs."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _assert_ok(response: requests.Response, step: str) -> dict:
    if not response.ok:
        raise RuntimeError(f"{step} failed: HTTP {response.status_code} {response.text}")
    return response.json()


def main() -> int:
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
    request_timeout = float(os.getenv("SMOKE_REQUEST_TIMEOUT_SECONDS", "45"))

    print("=" * 72)
    print("PHASE 6 SMOKE: CUSTOMER JOURNEY")
    print("=" * 72)

    try:
        health = _assert_ok(requests.get(f"{base_url}/api/health", timeout=request_timeout), "health")
        print("1) Health:", health.get("status"))

        counts = _assert_ok(requests.get(f"{base_url}/api/stats/customer-count", timeout=request_timeout), "customer count")
        print("2) Customer count:", counts.get("customer_count"))

        chat = _assert_ok(
            requests.post(
                f"{base_url}/api/ask",
                json={
                    "question": "Show me a maintenance schedule for a family SUV.",
                    "prefer_template": True,
                },
                timeout=request_timeout,
            ),
            "chatbot ask",
        )
        print("3) Chatbot answered:", bool(chat.get("answer")))

        triage = _assert_ok(
            requests.post(
                f"{base_url}/api/triage",
                json={
                    "session_id": "phase6-smoke-session",
                    "answers": {
                        "budget_max": 35000,
                        "use_case": "family",
                        "priority": "reliability",
                    },
                },
                timeout=request_timeout,
            ),
            "triage",
        )
        print("4) Triage matches:", len(triage.get("matches", [])))

        resume = _assert_ok(
            requests.post(
                f"{base_url}/api/resume-deal",
                json={
                    "name": "Phase6 Smoke",
                    "phone": "+15550009999",
                    "snapshot": {"journey": "phase6_smoke"},
                    "walkaway": True,
                    "source": "phase6-smoke",
                },
                timeout=request_timeout,
            ),
            "resume deal",
        )
        print("5) Resume token created:", bool(resume.get("resume_token")))

        prefs = _assert_ok(
            requests.post(
                f"{base_url}/api/customer-preferences/{resume.get('customer_id')}",
                json={
                    "preferences": [
                        {
                            "channel": "sms",
                            "is_enabled": True,
                            "contact_value": "+15550009999",
                        }
                    ]
                },
                timeout=request_timeout,
            ),
            "customer preferences",
        )
        print("6) Enabled channels:", len(prefs.get("preferences", [])))

        if health.get("twilio") == "up":
            followup = _assert_ok(
                requests.post(
                    f"{base_url}/api/followup/{resume.get('customer_id')}",
                    json={"override_message": "Thanks for visiting Imperial Cars."},
                    timeout=request_timeout,
                ),
                "followup",
            )
            print("7) Follow-up status:", followup.get("status"))
        else:
            print("7) Follow-up skipped: Twilio is not configured in this environment")

        print("=" * 72)
        print("SMOKE TEST PASSED")
        print("=" * 72)
        return 0
    except Exception as exc:
        print(f"SMOKE TEST FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
