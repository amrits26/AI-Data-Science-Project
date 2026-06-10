"""Customer service job workflows and follow-up preference orchestration."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from backend.app.agents.imperial_chatbot import ask_imperial
from backend.app.agents.twilio_multichannel import send_followup_by_preferences as dispatch_by_preferences
from backend.app.database import Customer, CustomerChannelPref, JobUpdate, ServiceJob, get_db_session

logger = logging.getLogger(__name__)

ALLOWED_CHANNELS = {"sms", "whatsapp", "email", "voice"}


def create_job(
    customer_id: int,
    vehicle_id: int | None,
    job_type: str,
    priority: str = "normal",
    description: str | None = None,
    due_date: date | None = None,
    salesperson_id: int | None = None,
) -> int | None:
    """Create a service job record."""
    db = get_db_session()
    try:
        job = ServiceJob(
            customer_id=customer_id,
            salesperson_id=salesperson_id,
            vehicle_id=vehicle_id,
            job_type=job_type,
            status="pending",
            priority=priority,
            description=description,
            due_date=due_date,
        )
        db.add(job)
        db.commit()
        return int(job.id)
    except Exception as exc:
        db.rollback()
        logger.warning("create_service_job_failed", extra={"error": str(exc)})
        return None
    finally:
        db.close()


def update_job_status(job_id: int, new_status: str, message: str | None = None) -> bool:
    """Update a job status and append a status-history row."""
    db = get_db_session()
    try:
        job = db.query(ServiceJob).filter(ServiceJob.id == job_id).first()
        if not job:
            return False

        previous_status = job.status
        job.status = new_status
        if new_status == "completed":
            job.completed_date = date.today()

        db.add(JobUpdate(job_id=job_id, status=new_status, message=message))
        db.commit()

        if previous_status != "waiting_insurance" and new_status == "waiting_insurance":
            followup_message = message or "Your deal is waiting for insurance verification. Please reply with the updated insurance details."
            send_followup_by_preferences(job.customer_id, followup_message)

        return True
    except Exception as exc:
        db.rollback()
        logger.warning("update_service_job_failed", extra={"job_id": job_id, "error": str(exc)})
        return False
    finally:
        db.close()


def get_customer_jobs(customer_id: int, status_filter: str | None = None) -> list[dict[str, Any]]:
    """Fetch service jobs for a customer, optionally filtered by status."""
    db = get_db_session()
    try:
        query = db.query(ServiceJob).filter(ServiceJob.customer_id == customer_id)
        if status_filter:
            query = query.filter(ServiceJob.status == status_filter)
        jobs = query.order_by(ServiceJob.created_at.desc()).all()
        return [
            {
                "id": j.id,
                "job_type": j.job_type,
                "status": j.status,
                "priority": j.priority,
                "created_at": j.created_at,
                "due_date": j.due_date,
                "completed_date": j.completed_date,
            }
            for j in jobs
        ]
    except Exception as exc:
        logger.warning("get_customer_jobs_failed", extra={"customer_id": customer_id, "error": str(exc)})
        return []
    finally:
        db.close()


def get_pending_jobs() -> list[dict[str, Any]]:
    """Fetch all pending jobs across customers."""
    db = get_db_session()
    try:
        jobs = db.query(ServiceJob).filter(ServiceJob.status == "pending").all()
        return [
            {
                "id": j.id,
                "customer_id": j.customer_id,
                "job_type": j.job_type,
                "priority": j.priority,
                "due_date": j.due_date,
            }
            for j in jobs
        ]
    except Exception as exc:
        logger.warning("get_pending_jobs_failed", extra={"error": str(exc)})
        return []
    finally:
        db.close()


def get_customer_channel_prefs(customer_id: int) -> list[dict[str, Any]]:
    """Return channel preference rows for a customer."""
    db = get_db_session()
    try:
        rows = (
            db.query(CustomerChannelPref)
            .filter(CustomerChannelPref.customer_id == customer_id)
            .order_by(CustomerChannelPref.channel.asc())
            .all()
        )
        return [
            {
                "id": int(r.id),
                "customer_id": int(r.customer_id),
                "channel": str(r.channel),
                "is_enabled": bool(r.is_enabled),
                "contact_value": r.contact_value,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]
    finally:
        db.close()


def upsert_customer_channel_prefs(customer_id: int, prefs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace preference rows for a customer with the provided set."""
    db = get_db_session()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise ValueError("Customer not found")

        db.query(CustomerChannelPref).filter(CustomerChannelPref.customer_id == customer_id).delete()

        normalized_channels: list[str] = []
        for pref in prefs:
            channel = str(pref.get("channel", "")).strip().lower()
            if channel not in ALLOWED_CHANNELS:
                raise ValueError(f"Unsupported channel '{channel}'")
            normalized_channels.append(channel)
            db.add(
                CustomerChannelPref(
                    customer_id=customer_id,
                    channel=channel,
                    is_enabled=bool(pref.get("is_enabled", False)),
                    contact_value=(str(pref.get("contact_value", "")).strip() or None),
                )
            )

        customer.preferred_channels = sorted(list(set(normalized_channels)))
        db.commit()
        return get_customer_channel_prefs(customer_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def send_followup_by_preferences(customer_id: int, message: str | None = None) -> dict[str, Any]:
    """Generate a message when needed and send through enabled channels."""
    db = get_db_session()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return {"status": "failed", "customer_id": customer_id, "error": "Customer not found"}

        final_message = (message or "").strip()
        if not final_message:
            prompt = (
                f"Write a concise and friendly dealership follow-up for {customer.name}. "
                "Keep it to 1-2 sentences and include a call to action."
            )
            llm_answer = ask_imperial(prompt)
            final_message = llm_answer or "Thank you for choosing Imperial Cars. Please reply when you are ready for the next step."

        result = dispatch_by_preferences(customer_id=customer_id, message=final_message)
        result["generated"] = message is None
        return result
    except Exception as exc:
        logger.exception("send_followup_by_preferences_failed")
        return {"status": "failed", "customer_id": customer_id, "error": str(exc)}
    finally:
        db.close()


def send_unified_followup(customer_id: int, override_message: str | None = None) -> dict[str, Any]:
    """Backward-compatible alias used by existing UI and bot paths."""
    result = send_followup_by_preferences(customer_id=customer_id, message=override_message)
    channels = result.get("channels", {})
    result["sms_status"] = channels.get("sms", {}).get("status", "not_sent")
    result["whatsapp_status"] = channels.get("whatsapp", {}).get("status", "not_sent")
    result["voice_status"] = channels.get("voice", {}).get("status", "not_sent")
    result["email_status"] = channels.get("email", {}).get("status", "not_sent")
    return result
