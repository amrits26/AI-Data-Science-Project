"""Backward-compatible shim for legacy Twilio imports.

Canonical follow-up delivery lives in `backend.app.agents.twilio_multichannel`.
This module re-exports the shared channel senders and preserves the older
`send_unified_followup(phone, email, message)` contract for stale imports.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.app.agents.twilio_multichannel import make_voice_call, send_email, send_sms, validate_phone


def send_unified_followup(
    customer_phone: str | None,
    customer_email: str | None,
    message: str,
) -> dict[str, Any]:
    """Legacy helper that fans out directly to SMS, voice, and email."""
    results: dict[str, Any] = {
        "status": "completed",
        "sms": None,
        "voice": None,
        "email": None,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    sent_count = 0
    attempted = 0

    if customer_phone:
        attempted += 1
        sms_result = send_sms(customer_phone, message[:160])
        results["sms"] = sms_result
        if sms_result.get("status") == "sent":
            sent_count += 1

    if customer_phone:
        attempted += 1
        voice_result = make_voice_call(customer_phone, f"Hi, {message} Thank you.")
        results["voice"] = voice_result
        if voice_result.get("status") == "initiated":
            sent_count += 1

    if customer_email:
        attempted += 1
        email_result = send_email(customer_email, "Imperial Cars Follow-Up", f"<p>{message}</p>")
        results["email"] = email_result
        if email_result.get("status") == "sent":
            sent_count += 1

    if attempted == 0 or sent_count == 0:
        results["status"] = "failed"
        results["summary"] = "No follow-up channels succeeded"
    elif sent_count < attempted:
        results["status"] = "partial"
        results["summary"] = f"Sent via {sent_count}/{attempted} channels"
    else:
        results["status"] = "completed"
        results["summary"] = f"Sent via all {sent_count} channels"

    return results


__all__ = [
    "validate_phone",
    "send_sms",
    "make_voice_call",
    "send_email",
    "send_unified_followup",
]
