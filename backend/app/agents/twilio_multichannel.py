"""Twilio multi-channel delivery for customer follow-up workflows."""

from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import requests

from backend.app.database import Customer, CustomerChannelPref, FollowupLog, get_db_session

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "").strip()
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "").strip() or f"whatsapp:{TWILIO_PHONE_NUMBER}"

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER).strip()

ALLOWED_CHANNELS = {"sms", "whatsapp", "email", "voice"}


def validate_phone(phone: str | None) -> str | None:
    """Normalize a phone number to E.164 when possible."""
    if not phone:
        return None
    cleaned = str(phone).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if cleaned.startswith("+") and cleaned[1:].isdigit() and len(cleaned) >= 11:
        return cleaned
    if cleaned.isdigit() and len(cleaned) == 10:
        return f"+1{cleaned}"
    if cleaned.isdigit() and len(cleaned) == 11 and cleaned.startswith("1"):
        return f"+{cleaned}"
    return None


def _twilio_post(endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        return {"status": "failed", "error": "Twilio credentials not configured"}
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/{endpoint}"
    response = requests.post(url, data=data, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=15)
    response.raise_for_status()
    return response.json()


def send_sms(to_number: str, message: str) -> dict[str, Any]:
    """Send SMS via Twilio."""
    recipient = validate_phone(to_number)
    if not recipient:
        return {"status": "failed", "channel": "sms", "error": "Invalid phone number"}
    if not TWILIO_PHONE_NUMBER:
        return {"status": "failed", "channel": "sms", "error": "TWILIO_PHONE_NUMBER is missing"}
    try:
        payload = {
            "From": TWILIO_PHONE_NUMBER,
            "To": recipient,
            "Body": message[:1600],
        }
        result = _twilio_post("Messages.json", payload)
        return {"status": "sent", "channel": "sms", "sid": result.get("sid"), "recipient": recipient}
    except Exception as exc:
        logger.warning("twilio_sms_failed", extra={"to": recipient, "error": str(exc)})
        return {"status": "failed", "channel": "sms", "error": str(exc), "recipient": recipient}


def send_whatsapp(to_number: str, message: str) -> dict[str, Any]:
    """Send WhatsApp message via Twilio."""
    recipient = validate_phone(to_number)
    if not recipient:
        return {"status": "failed", "channel": "whatsapp", "error": "Invalid phone number"}
    if not TWILIO_WHATSAPP_NUMBER:
        return {"status": "failed", "channel": "whatsapp", "error": "TWILIO_WHATSAPP_NUMBER is missing"}
    try:
        payload = {
            "From": TWILIO_WHATSAPP_NUMBER,
            "To": f"whatsapp:{recipient}",
            "Body": message[:4096],
        }
        result = _twilio_post("Messages.json", payload)
        return {"status": "sent", "channel": "whatsapp", "sid": result.get("sid"), "recipient": recipient}
    except Exception as exc:
        logger.warning("twilio_whatsapp_failed", extra={"to": recipient, "error": str(exc)})
        return {"status": "failed", "channel": "whatsapp", "error": str(exc), "recipient": recipient}


def make_voice_call(to_number: str, message: str) -> dict[str, Any]:
    """Initiate a voice call via Twilio with a short TwiML payload."""
    recipient = validate_phone(to_number)
    if not recipient:
        return {"status": "failed", "channel": "voice", "error": "Invalid phone number"}
    if not TWILIO_PHONE_NUMBER:
        return {"status": "failed", "channel": "voice", "error": "TWILIO_PHONE_NUMBER is missing"}
    try:
        twiml = (
            "<?xml version='1.0' encoding='UTF-8'?>"
            f"<Response><Say voice='alice'>{message}</Say><Pause length='1'/><Say>Thank you from Imperial Cars.</Say></Response>"
        )
        payload = {
            "From": TWILIO_PHONE_NUMBER,
            "To": recipient,
            "Twiml": twiml,
        }
        result = _twilio_post("Calls.json", payload)
        return {"status": "initiated", "channel": "voice", "sid": result.get("sid"), "recipient": recipient}
    except Exception as exc:
        logger.warning("twilio_voice_failed", extra={"to": recipient, "error": str(exc)})
        return {"status": "failed", "channel": "voice", "error": str(exc), "recipient": recipient}


def send_email(to_address: str, subject: str, body: str) -> dict[str, Any]:
    """Send email using SMTP credentials from environment."""
    email = str(to_address or "").strip()
    if not email:
        return {"status": "failed", "channel": "email", "error": "Missing email address"}
    if not all([SMTP_SERVER, SMTP_USER, SMTP_PASSWORD, SMTP_FROM]):
        return {"status": "failed", "channel": "email", "error": "SMTP settings are incomplete"}
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = email
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, email, msg.as_string())

        return {"status": "sent", "channel": "email", "recipient": email}
    except Exception as exc:
        logger.warning("smtp_send_failed", extra={"to": email, "error": str(exc)})
        return {"status": "failed", "channel": "email", "error": str(exc), "recipient": email}


def _resolve_contact(channel: str, pref_contact: str | None, customer: Customer) -> str | None:
    channel = channel.lower().strip()
    if channel in {"sms", "whatsapp", "voice"}:
        return pref_contact or customer.phone
    if channel == "email":
        return pref_contact or customer.email
    return None


def _log_channel_attempt(customer_id: int, channel: str, message: str, result: dict[str, Any]) -> None:
    db = get_db_session()
    try:
        db.add(
            FollowupLog(
                customer_id=customer_id,
                channel=channel,
                status=str(result.get("status", "failed")),
                message_body=message,
                recipient=result.get("recipient"),
                response=result,
                error=result.get("error"),
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("followup_log_failed", extra={"customer_id": customer_id, "channel": channel, "error": str(exc)})
    finally:
        db.close()


def send_followup_by_preferences(customer_id: int, message: str) -> dict[str, Any]:
    """Dispatch follow-up using the enabled customer channel preferences."""
    db = get_db_session()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return {"status": "failed", "customer_id": customer_id, "error": "Customer not found"}

        prefs = (
            db.query(CustomerChannelPref)
            .filter(CustomerChannelPref.customer_id == customer_id, CustomerChannelPref.is_enabled.is_(True))
            .all()
        )

        # Backward-compatible fallback if no explicit preference rows exist.
        if not prefs and customer.preferred_channels:
            for channel in customer.preferred_channels:
                if str(channel).lower().strip() in ALLOWED_CHANNELS:
                    prefs.append(
                        CustomerChannelPref(
                            customer_id=customer_id,
                            channel=str(channel).lower().strip(),
                            is_enabled=True,
                            contact_value=None,
                        )
                    )

        if not prefs:
            return {
                "status": "failed",
                "customer_id": customer_id,
                "error": "No enabled channel preferences found",
            }

        attempts: dict[str, Any] = {}
        for pref in prefs:
            channel = str(pref.channel or "").lower().strip()
            if channel not in ALLOWED_CHANNELS:
                continue
            contact = _resolve_contact(channel, pref.contact_value, customer)
            if not contact:
                attempts[channel] = {"status": "failed", "channel": channel, "error": "No contact value available"}
                _log_channel_attempt(customer_id, channel, message, attempts[channel])
                continue

            if channel == "sms":
                result = send_sms(contact, message)
            elif channel == "whatsapp":
                result = send_whatsapp(contact, message)
            elif channel == "voice":
                result = make_voice_call(contact, message)
            else:
                result = send_email(contact, "Imperial Cars Follow-up", f"<p>{message}</p>")

            attempts[channel] = result
            _log_channel_attempt(customer_id, channel, message, result)

        sent_count = sum(1 for x in attempts.values() if x.get("status") in {"sent", "initiated"})
        total = len(attempts)
        if total == 0 or sent_count == 0:
            overall = "failed"
        elif sent_count == total:
            overall = "completed"
        else:
            overall = "partial"

        return {
            "status": overall,
            "customer_id": customer_id,
            "message": message,
            "channels": attempts,
            "summary": f"Sent via {sent_count}/{total} enabled channels",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as exc:
        logger.exception("send_followup_by_preferences_failed")
        return {"status": "failed", "customer_id": customer_id, "error": str(exc)}
    finally:
        db.close()
