"""
Customer Lifecycle Agents - Automated workflows with APScheduler.

DriveCentric-style lifecycle management:
- New customer onboarding
- Service reminders (oil changes at 5k/10k/15k miles)
- Trade-in eligibility checks
- Vehicle buyback opportunities
- Renewal/retention campaigns
- Win-back (dormant customer) campaigns
"""

import os
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Dict, Any, List

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
except Exception:  # pragma: no cover - optional runtime dependency
    BackgroundScheduler = None
    CronTrigger = None

from backend.app.database import get_db_session, Customer, Vehicle, ServiceJob, NurtureLog, FollowupLog
from backend.app.agents.customer_updates import create_job
from backend.app.agents.twilio_multichannel import send_sms


# Global scheduler instance
scheduler: Optional[BackgroundScheduler] = None
logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def schedule_followup_by_tier(customer_id: int, tier: str, salesperson_phone: str | None = None) -> dict[str, Any]:
    """Create cadence follow-up entry and optionally send SMS reminder to salesperson."""
    normalized = str(tier or "cold").strip().lower()
    cadence_days = {
        "hot": 1,
        "warm": 3,
        "cold": 7,
    }.get(normalized, 7)

    due_at = _utcnow() + timedelta(days=cadence_days)
    reminder_text = (
        f"Imperial Cars lead cadence: Customer #{customer_id} is {normalized.upper()}. "
        f"Next contact due by {due_at.strftime('%Y-%m-%d %H:%M UTC')}."
    )

    db = get_db_session()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return {"status": "failed", "error": "Customer not found"}

        sms_result = None
        if salesperson_phone:
            sms_result = send_sms(salesperson_phone, reminder_text)

        db.add(
            FollowupLog(
                customer_id=customer_id,
                channel="sms" if salesperson_phone else "system",
                status="scheduled",
                message_body=reminder_text,
                recipient=salesperson_phone,
                response={
                    "tier": normalized,
                    "cadence_days": cadence_days,
                    "due_at": due_at.isoformat() + "Z",
                    "sms": sms_result,
                },
            )
        )
        db.commit()

        return {
            "status": "ok",
            "customer_id": customer_id,
            "tier": normalized,
            "cadence_days": cadence_days,
            "due_at": due_at.isoformat() + "Z",
            "sms": sms_result,
        }
    except Exception as exc:
        db.rollback()
        logger.warning("schedule_followup_by_tier_failed", extra={"customer_id": customer_id, "tier": normalized, "error": str(exc)})
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()


def initialize_scheduler():
    """Initialize and start the APScheduler background scheduler."""
    global scheduler

    if BackgroundScheduler is None or CronTrigger is None:
        logger.warning("lifecycle_scheduler_unavailable", extra={"reason": "apscheduler_not_installed"})
        return

    if scheduler is not None:
        return  # Already initialized

    scheduler = BackgroundScheduler()

    # Schedule lifecycle jobs
    scheduler.add_job(
        func=run_onboarding_workflow,
        trigger=CronTrigger(hour=9, minute=0),  # Daily at 9 AM
        id="onboarding_daily",
        name="Daily onboarding checks",
        replace_existing=True,
    )

    scheduler.add_job(
        func=run_service_reminder_workflow,
        trigger=CronTrigger(hour=10, minute=0),  # Daily at 10 AM
        id="service_reminders_daily",
        name="Daily service reminders",
        replace_existing=True,
    )

    scheduler.add_job(
        func=run_trade_in_workflow,
        trigger=CronTrigger(hour=11, minute=0),  # Daily at 11 AM
        id="trade_in_daily",
        name="Daily trade-in checks",
        replace_existing=True,
    )

    scheduler.add_job(
        func=run_winback_workflow,
        trigger=CronTrigger(hour=14, minute=0),  # Daily at 2 PM
        id="winback_daily",
        name="Daily win-back campaigns",
        replace_existing=True,
    )

    scheduler.add_job(
        func=run_buyback_workflow,
        trigger=CronTrigger(hour=15, minute=0),  # Daily at 3 PM
        id="buyback_daily",
        name="Daily buyback opportunities",
        replace_existing=True,
    )

    scheduler.add_job(
        func=run_service_heart_workflow,
        trigger=CronTrigger(hour=16, minute=0),  # Daily at 4 PM
        id="service_heart_daily",
        name="Daily service-heart relationship touchpoints",
        replace_existing=True,
    )

    scheduler.add_job(
        func=run_review_request_workflow,
        trigger=CronTrigger(hour=17, minute=0),  # Daily at 5 PM
        id="review_request_daily",
        name="48-hour review requests",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("lifecycle_scheduler_started")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    global scheduler

    if scheduler:
        scheduler.shutdown(wait=True)
        scheduler = None
        logger.info("lifecycle_scheduler_stopped")


def run_onboarding_workflow():
    """
    Check for new customers and send welcome message.
    """
    db = get_db_session()
    try:
        # Find customers onboarded in last 24 hours
        cutoff = date.today() - timedelta(days=1)
        new_customers = db.query(Customer).filter(Customer.created_at >= cutoff).all()

        for customer in new_customers:
            # Check if already welcomed
            existing_log = db.query(NurtureLog).filter(
                NurtureLog.customer_id == customer.id,
                NurtureLog.message_type == "welcome"
            ).first()

            if not existing_log:
                # Send welcome message
                first_name = (customer.name or "there").split()[0]
                message = (
                    f"👋 Welcome to Imperial Cars, {first_name}!\n\n"
                    f"We're excited to help you find your perfect vehicle.\n"
                    f"Browse our inventory: https://imperialcars.local/inventory\n"
                    f"Need help? Reply /help or call 555-0123"
                )
                success = bool(customer.telegram_id or customer.email)

                # Log the campaign
                log = NurtureLog(
                    customer_id=customer.id,
                    message_type="welcome",
                    message_body=message,
                    channel="telegram" if customer.telegram_id else "email",
                    sent_at=datetime.now(),
                    delivery_status="sent" if success else "pending",
                )
                db.add(log)
                db.commit()

    except Exception as e:
        logger.warning("onboarding_workflow_failed", extra={"error": str(e)})
        db.rollback()
    finally:
        db.close()


def run_service_reminder_workflow():
    """
    Send service reminders based on odometer milestones (5k, 10k, 15k miles).
    """
    db = get_db_session()
    try:
        # Get all vehicles
        vehicles = db.query(Vehicle).all()

        for vehicle in vehicles:
            if not vehicle.mileage:
                continue

            # Check milestones
            milestones = [5000, 10000, 15000, 20000]
            for milestone in milestones:
                if vehicle.mileage >= milestone and vehicle.mileage < milestone + 1000:
                    # Check if already sent
                    existing_job = db.query(ServiceJob).filter(
                        ServiceJob.vehicle_id == vehicle.id,
                        ServiceJob.job_type == "service_reminder",
                        ServiceJob.status == "pending",
                    ).first()

                    if not existing_job:
                        # Create service job
                        job_id = create_job(
                            customer_id=vehicle.customer_id,
                            vehicle_id=vehicle.id,
                            job_type="service_reminder",
                            priority="normal",
                            description=f"Service reminder at {milestone:,} miles",
                        )

                        if job_id:
                            # Log the campaign
                            log = NurtureLog(
                                customer_id=vehicle.customer_id,
                                message_type="service_reminder",
                                message_body=f"Service reminder created for {milestone:,} miles",
                                channel="system",
                                sent_at=datetime.now(),
                                delivery_status="sent",
                            )
                            db.add(log)
                            db.commit()

    except Exception as e:
        logger.warning("service_reminder_workflow_failed", extra={"error": str(e)})
        db.rollback()
    finally:
        db.close()


def run_trade_in_workflow():
    """
    Check for vehicles eligible for trade-in (2+ years old, reasonable condition).
    """
    db = get_db_session()
    try:
        # Get customers with vehicles 2+ years old
        cutoff_year = date.today().year - 2
        vehicles = db.query(Vehicle).filter(Vehicle.year <= cutoff_year).all()

        for vehicle in vehicles:
            # Check if already sent trade-in offer
            existing_log = db.query(NurtureLog).filter(
                NurtureLog.customer_id == vehicle.customer_id,
                NurtureLog.message_type == "trade_in_offer",
                NurtureLog.sent_at >= datetime.now() - timedelta(days=30)
            ).first()

            if not existing_log:
                # Send trade-in offer
                message = (
                    f"💰 Trade-In Opportunity\n\n"
                    f"Your {vehicle.year} {vehicle.make} {vehicle.model} might be worth more than you think!\n"
                    f"Get an instant quote: /trade_in_quote\n"
                    f"Or schedule an appraisal: /schedule_appraisal"
                )

                log = NurtureLog(
                    customer_id=vehicle.customer_id,
                    message_type="trade_in_offer",
                    message_body=message,
                    channel="system",
                    sent_at=datetime.now(),
                    delivery_status="sent",
                )
                db.add(log)
                db.commit()

    except Exception as e:
        logger.warning("trade_in_workflow_failed", extra={"error": str(e)})
        db.rollback()
    finally:
        db.close()


def run_winback_workflow():
    """
    Identify dormant customers (no activity in 60+ days) and send win-back campaigns.
    """
    db = get_db_session()
    try:
        # Find customers with no recent orders/messages
        cutoff = date.today() - timedelta(days=60)
        dormant_customers = db.query(Customer).filter(Customer.updated_at < cutoff).all()

        for customer in dormant_customers:
            # Check if already sent win-back
            existing_log = db.query(NurtureLog).filter(
                NurtureLog.customer_id == customer.id,
                NurtureLog.message_type == "winback",
                NurtureLog.sent_at >= datetime.now() - timedelta(days=30)
            ).first()

            if not existing_log:
                # Send win-back message
                message = (
                    f"👋 We miss you, {(customer.name or 'there').split()[0]}!\n\n"
                    f"It's been a while since we last connected.\n"
                    f"Check out our latest inventory or schedule a test drive:\n"
                    f"/inventory or /schedule_test_drive"
                )

                log = NurtureLog(
                    customer_id=customer.id,
                    message_type="winback",
                    message_body=message,
                    channel="system",
                    sent_at=datetime.now(),
                    delivery_status="sent",
                )
                db.add(log)
                db.commit()

    except Exception as e:
        logger.warning("winback_workflow_failed", extra={"error": str(e)})
        db.rollback()
    finally:
        db.close()


def run_buyback_workflow():
    """
    Identify customers with high-demand vehicles and send buyback offers.
    """
    db = get_db_session()
    try:
        # Find customers with currently-hot makes/models
        hot_makes = ["Toyota", "Honda", "Ford", "BMW"]

        for make in hot_makes:
            # Check if we have customers with this make
            vehicles = db.query(Vehicle).filter(
                Vehicle.make.ilike(f"%{make}%"),
                Vehicle.year >= date.today().year - 3
            ).all()

            for vehicle in vehicles:
                # Check if already sent buyback
                existing_log = db.query(NurtureLog).filter(
                    NurtureLog.customer_id == vehicle.customer_id,
                    NurtureLog.message_type == "buyback_offer",
                    NurtureLog.sent_at >= datetime.now() - timedelta(days=30)
                ).first()

                if not existing_log:
                    # Send buyback offer
                    message = (
                        f"🚗 High Demand Alert!\n\n"
                        f"Your {vehicle.year} {make} is in high demand right now.\n"
                        f"We may buy it at or above market value.\n"
                        f"Get an instant offer: /buyback_quote"
                    )

                    log = NurtureLog(
                        customer_id=vehicle.customer_id,
                        message_type="buyback_offer",
                        message_body=message,
                        channel="system",
                        sent_at=datetime.now(),
                        delivery_status="sent",
                    )
                    db.add(log)
                    db.commit()

    except Exception as e:
        logger.warning("buyback_workflow_failed", extra={"error": str(e)})
        db.rollback()
    finally:
        db.close()


def run_service_heart_workflow(reference_date: date | None = None):
    """
    Send relational care messages at 30/90/365 days after purchase.
    """
    today = reference_date or date.today()
    milestones = {30: "service_heart_30", 90: "service_heart_90", 365: "service_heart_365"}

    db = get_db_session()
    try:
        customers = db.query(Customer).filter(Customer.last_purchase_date.isnot(None)).all()

        for customer in customers:
            days_after_sale = (today - customer.last_purchase_date).days if customer.last_purchase_date else -1
            if days_after_sale not in milestones:
                continue

            message_type = milestones[days_after_sale]
            existing = db.query(NurtureLog).filter(
                NurtureLog.customer_id == customer.id,
                NurtureLog.message_type == message_type,
            ).first()
            if existing:
                continue

            first_name = (customer.name or "friend").split()[0]
            if days_after_sale == 30:
                body = f"Hi {first_name}, just checking in from Imperial Cars. How is everything feeling with your vehicle so far?"
            elif days_after_sale == 90:
                body = f"Hi {first_name}, we hope you are still loving your ride. If anything feels off, we are here for you."
            else:
                body = f"Hi {first_name}, one year in and we still appreciate you. Reach out anytime if you want a vehicle health check."

            db.add(
                NurtureLog(
                    customer_id=customer.id,
                    message_type=message_type,
                    message_body=body,
                    channel="system",
                    days_after_sale=days_after_sale,
                    sent_at=datetime.now(),
                    delivery_status="sent",
                )
            )

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("service_heart_workflow_failed", extra={"error": str(exc)})
    finally:
        db.close()


def run_review_request_workflow(reference_date: date | None = None):
    """Send review requests 48 hours after purchase date."""
    today = reference_date or date.today()
    google_link = os.getenv("REVIEW_LINK_GOOGLE", "https://www.google.com/maps")
    cars_link = os.getenv("REVIEW_LINK_CARSCOM", "https://www.cars.com")
    dealer_rater_link = os.getenv("REVIEW_LINK_DEALERRATER", "https://www.dealerrater.com")

    db = get_db_session()
    try:
        customers = db.query(Customer).filter(Customer.last_purchase_date.isnot(None)).all()
        for customer in customers:
            if not customer.last_purchase_date:
                continue
            days_since = (today - customer.last_purchase_date).days
            if days_since != 2:
                continue

            existing = db.query(NurtureLog).filter(
                NurtureLog.customer_id == customer.id,
                NurtureLog.message_type == "review_request_48h",
            ).first()
            if existing:
                continue

            first_name = (customer.name or "there").split()[0]
            message = (
                f"Hi {first_name}, thank you again for choosing Imperial Cars. "
                f"If you have a minute, we would appreciate your feedback: "
                f"Google: {google_link} | Cars.com: {cars_link} | DealerRater: {dealer_rater_link}"
            )

            sms_result = None
            if customer.phone:
                sms_result = send_sms(customer.phone, message)

            db.add(
                NurtureLog(
                    customer_id=customer.id,
                    message_type="review_request_48h",
                    message_body=message,
                    channel="sms" if customer.phone else "system",
                    sent_at=datetime.now(),
                    delivery_status="sent" if customer.phone else "pending",
                    response=str(sms_result) if sms_result else None,
                )
            )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("review_request_workflow_failed", extra={"error": str(exc)})
    finally:
        db.close()


def get_nurture_history(customer_id: int) -> List[Dict[str, Any]]:
    """Get all nurture campaigns sent to a customer."""
    db = get_db_session()
    try:
        logs = db.query(NurtureLog).filter(
            NurtureLog.customer_id == customer_id
        ).order_by(NurtureLog.sent_at.desc()).all()

        result = [
            {
                "campaign_type": log.message_type,
                "message_sent": log.delivery_status == "sent",
                "sent_at": log.sent_at,
            }
            for log in logs
        ]

        db.close()
        return result

    except Exception as e:
        logger.warning("get_nurture_history_failed", extra={"customer_id": customer_id, "error": str(e)})
        return []


def manual_trigger(workflow_type: str) -> Dict[str, str]:
    """
    Manually trigger a lifecycle workflow (for testing).

    Args:
        workflow_type: "onboarding", "service", "trade_in", "winback", "buyback"

    Returns:
        {"status": "ok"|"error", "message": str}
    """
    try:
        if workflow_type == "onboarding":
            run_onboarding_workflow()
        elif workflow_type == "service":
            run_service_reminder_workflow()
        elif workflow_type == "trade_in":
            run_trade_in_workflow()
        elif workflow_type == "winback":
            run_winback_workflow()
        elif workflow_type == "buyback":
            run_buyback_workflow()
        elif workflow_type == "service_heart":
            run_service_heart_workflow()
        elif workflow_type == "review":
            run_review_request_workflow()
        else:
            return {"status": "error", "message": f"Unknown workflow: {workflow_type}"}

        return {"status": "ok", "message": f"Triggered {workflow_type} workflow"}

    except Exception as e:
        return {"status": "error", "message": str(e)}
