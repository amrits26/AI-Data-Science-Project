

import os
from pathlib import Path
from datetime import datetime
import sqlite3

from fastapi import APIRouter
from backend.app.agents.vehicle_intel import get_vehicle_breakdown, get_similar_vehicles

router = APIRouter(prefix="/api", tags=["pipeline"])

# --- STATUS DASHBOARD ENDPOINT ---
@router.get("/dashboard")
async def dashboard():
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    heartbeat_file = PROJECT_ROOT / "data" / "logs" / "heartbeat.txt"
    watchdog_log = PROJECT_ROOT / "data" / "logs" / "watchdog.log"
    watchdog_db = PROJECT_ROOT / "data" / "logs" / "watchdog.db"
    status = {}
    # Heartbeat
    if heartbeat_file.exists():
        try:
            with open(heartbeat_file) as f:
                last_beat = float(f.read().strip())
            status["heartbeat_age_sec"] = round(_utcnow().timestamp() - last_beat, 1)
        except Exception:
            status["heartbeat_age_sec"] = None
    else:
        status["heartbeat_age_sec"] = None
    # Watchdog log tail
    if watchdog_log.exists():
        with open(watchdog_log, "r") as f:
            lines = f.readlines()[-10:]
        status["watchdog_log_tail"] = lines
    else:
        status["watchdog_log_tail"] = []
    # Recent watchdog events
    if watchdog_db.exists():
        try:
            conn = sqlite3.connect(str(watchdog_db))
            rows = conn.execute("SELECT timestamp, event_type, action_taken FROM watchdog_events ORDER BY timestamp DESC LIMIT 10").fetchall()
            conn.close()
            status["recent_events"] = [dict(timestamp=r[0], event_type=r[1], action=r[2]) for r in rows]
        except Exception:
            status["recent_events"] = []
    else:
        status["recent_events"] = []
    return status
## (removed duplicate future import)
from backend.app.agents.vehicle_intel import get_vehicle_breakdown, get_similar_vehicles
# --- VEHICLE VISUALIZATIONS: Aggregate all data for visualizations panel ---
@router.get("/visualizations/{stock_number}")
async def get_visualizations(stock_number: str):
    db = get_db_session()
    try:
        car = db.query(Car).filter(Car.stock_number == stock_number).first()
        if not car:
            return {"error": "Vehicle not found"}

        # ValueComparisonGauge: price, msrp, kbb, our price, savings
        vehicle = {
            "price": car.price if hasattr(car, "price") else car.msrp or car.used_avg_price or 0,
            "msrp": car.msrp or 0,
            "kbb": getattr(car, "kbb_value", None) or car.msrp or 0,  # Placeholder for KBB
            "our_price": car.price if hasattr(car, "price") else car.msrp or car.used_avg_price or 0,
            "savings": (car.msrp or 0) - (car.price if hasattr(car, "price") else car.msrp or car.used_avg_price or 0),
            "year": car.year,
            "make": car.make,
            "model": car.model,
            "trim": car.trim,
        }

        # ComparisonBars: compare to similar vehicles
        similar = get_similar_vehicles(stock_number, max_results=2)
        comparison = None
        if similar:
            comparison = {
                "left": {
                    "year": car.year,
                    "make": car.make,
                    "model": car.model,
                    "trim": car.trim,
                    "price": car.price if hasattr(car, "price") else car.msrp or car.used_avg_price or 0,
                    "horsepower": car.horsepower,
                    "torque": car.torque,
                    "mpg_highway": car.mpg_highway,
                    "towing_capacity": car.towing_capacity,
                },
                "right": {
                    "year": similar[0].get("year"),
                    "make": similar[0].get("make"),
                    "model": similar[0].get("model"),
                    "trim": similar[0].get("trim"),
                    "price": similar[0].get("price"),
                    "horsepower": similar[0].get("horsepower"),
                    "torque": similar[0].get("torque"),
                    "mpg_highway": similar[0].get("mpg_highway"),
                    "towing_capacity": similar[0].get("towing_capacity"),
                },
            }

        # OwnershipCostChart: placeholder (real data would come from cost API)
        # For now, just echo vehicle

        # TrendingNow: top 3 similar vehicles (social proof)
        trending = similar[:3]

        # VehicleActivity: placeholder
        activity = {
            "views": 42,  # TODO: wire to real analytics
            "inquiries": 7,
            "lotSince": car.last_seen.isoformat() if car.last_seen else None,
            "isPopular": True,
        }

        # SafetyStars: NHTSA rating
        safety = {"rating": int(car.safety_rating or 0)}

        # ReliabilityGauge: reliability score
        reliability = {"score": int(car.reliability_score or 0)}

        # WillItFitVisualization: dimensions
        fit = {
            "length": car.length or 0,
            "width": car.width or 0,
            "type": "car",  # TODO: classify type
            "fitInfo": {"parking": True, "garage": True, "clearance": int((108 - (car.width or 0)) / 2)},
        }

        return {
            "vehicle": vehicle,
            "comparison": comparison,
            "trending": trending,
            "activity": activity,
            "safety": safety,
            "reliability": reliability,
            "fit": fit,
        }
    finally:
        db.close()

from backend.app.database.db import get_db_session
from backend.app.database.models import Lead
# --- LEADS: Retrieve recent leads for dashboard ---
from pydantic import BaseModel, ConfigDict

class LeadOut(BaseModel):
    id: int
    name: str | None
    phone: str | None
    email: str | None
    preferred_contact_time: str | None
    vehicle_interest: str | None
    created_at: datetime
    session_id: str | None

    model_config = ConfigDict(from_attributes=True)

@router.get("/leads", response_model=list[LeadOut])
async def get_recent_leads(limit: int = 20):
    db = get_db_session()
    try:
        leads = db.query(Lead).order_by(Lead.created_at.desc()).limit(limit).all()
        return leads
    finally:
        db.close()


import json
import asyncio
import csv
import os
import tempfile
import hashlib
import logging
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone

from pathlib import Path
from typing import Any
from fastapi import Body, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
"""API routes for analytics, dealership tools, and customer engagement workflows."""

# --- FEEDBACK: Feedback endpoint ---
from backend.app.schemas.requests import FeedbackRequest

@router.post("/feedback")
async def post_feedback(payload: FeedbackRequest):
    log_path = os.path.join("data", "feedback.jsonl")
    entry = payload.dict()
    entry["timestamp"] = datetime.now().isoformat()
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        return {"status": "error", "error": str(e)}
    return {"status": "ok"}

import uuid

from datetime import date, datetime, timedelta, timezone

from pathlib import Path

from typing import Any

# FastAPI imports must come before router definition

from fastapi import APIRouter, Body, File, Form, Header, HTTPException, Request, UploadFile

from fastapi.responses import FileResponse, JSONResponse, Response

"""API routes for analytics, dealership tools, and customer engagement workflows."""


# --- FAQ HARVESTING: Unanswered questions endpoint ---
@router.get("/unanswered")
async def get_unanswered():
    log_path = os.path.join("data", "unanswered_questions.jsonl")
    if not os.path.exists(log_path):
        return []
    lines = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                lines.append(json.loads(line))
            except Exception:
                continue
    return lines[-50:]

import io

from backend.app.core.platform_compat import patch_platform_machine_for_windows

patch_platform_machine_for_windows()

import pandas as pd

import requests

from sqlalchemy import func, text, tuple_

from fastapi import APIRouter, Body, File, Form, Header, HTTPException, Request, UploadFile

from fastapi.responses import FileResponse, JSONResponse, Response

from backend.app.agents.customer_updates import (

get_customer_channel_prefs,
    send_followup_by_preferences,
    upsert_customer_channel_prefs,
)
from backend.app.agents.dealership_tools import (

appraise_trade_in,
    calculate_lead_quality_score,
    daily_briefing,
    list_deals,
    score_leads_from_csv,
    track_sales_stage,
    update_deal_status,
)
from backend.app.agents.carfax_ingestor import lookup_vin_public, parse_carfax_pdf_bytes

from backend.app.agents.document_ingestion import DOC_TYPES, process_document_image

from backend.app.agents.finance_calibration import calibrate_credit_tiers, load_credit_tier_status

from backend.app.agents.finance_agent import payment_ladder

from backend.app.agents.inventory_scraper import check_detail_url_live, run_inventory_scrape

from backend.app.agents.knowledge_base.ingest import ingest_knowledge_base

from backend.app.agents.knowledge_base.query import query_knowledge_base

from backend.app.agents.negotiation import negotiation_assistant

from backend.app.agents.payout_generator import generate_sales_payout

from backend.app.agents.vehicle_intel import get_similar_vehicles, get_vehicle_breakdown, get_vehicle_photos

from backend.app.agents.buyers_guide import generate_buyers_guide_pdf

from backend.app.agents.imperial_chatbot import ask_imperial
from backend.app.skills.live_car_finder import LiveCarFinder

from backend.app.agents.math_tools import (

break_even_miles,
    lease_calculator,
    lease_vs_buy,
    loan_calculator,
    trade_in_equity,
)
from backend.app.agents.nhtsa_api import MAKES_URL, decode_vin

from backend.app.agents.orchestrator import AnalysisOrchestrator

from backend.app.agents.training_feedback import build_training_report, update_feedback

from backend.app.agents.twilio_multichannel import send_sms

from backend.app.database import Car, Customer, DailyGoal, FollowupLog, LeadContact, MarketPrice, ResumeDealSession, SalesStageEvent, ServiceVideo, TriageSession, Vehicle, get_db_session

from backend.app.database.db import ensure_inventory_schema, inventory_status_summary

from backend.app.core.config import ADMIN_API_SECRET, BREAK_EVEN_MONTH, INVENTORY_STALE_HOURS, SERVICE_VIDEO_APPROVAL_SECRET

from backend.app.schemas.requests import (

BreakEvenMilesRequest,
    DailyGoalsRequest,
    DealStatusUpdateRequest,
    DealStageRequest,
    FeedbackRequest,
    FinanceEstimateRequest,
    FinanceLadderRequest,
    KnowledgeQueryRequest,
    LeaseRequest,
    LeaseVsBuyRequest,
    LeadQualityRequest,
    LoanRequest,
    NegotiationRequest,
    PayoutRequest,
    SalespersonPinRequest,
    ServiceVideoApprovalRequest,
    SimilarVehicleRequest,
    TradeInEquityRequest,
    TradeInEstimateRequest,
    VehicleLookupRequest,
)


# --- FAQ HARVESTING: Unanswered questions endpoint ---

MAX_SIZE_MB = 50
SERVICE_VIDEO_DIR = Path(os.getenv("SERVICE_VIDEO_DIR", "data/service_videos")).resolve()
SERVICE_VIDEO_MAX_SIZE_BYTES = 200 * 1024 * 1024
SERVICE_VIDEO_ALLOWED_MIME_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-msvideo",
    "video/x-matroska",
}

logger = logging.getLogger(__name__)


def _require_admin_secret_if_configured(x_admin_secret: str | None) -> None:
    configured = (ADMIN_API_SECRET or "").strip()
    if not configured:
        return
    provided = (x_admin_secret or "").strip()
    if not provided or not secrets.compare_digest(provided, configured):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _triage_fit_score(car: Car, budget_max: float, use_case: str, priority: str) -> float:
    """Heuristic matcher for first-interaction triage recommendations."""
    price = float(car.msrp or car.used_avg_price or 0)
    safety = float(car.safety_rating or 0)
    reliability = float(car.reliability_score or 0)
    mpg = float(car.mpg_highway or 0)
    horsepower = float(car.horsepower or 0)

    if budget_max > 0:
        budget_score = max(0.0, 1.0 - abs(price - budget_max) / max(budget_max, 1.0))
    else:
        budget_score = 0.5

    use_score = 0.5
    normalized_use = use_case.strip().lower()
    if normalized_use == "family":
        use_score = min(1.0, ((safety / 5.0) * 0.6) + ((reliability / 100.0) * 0.4))
    elif normalized_use == "commute":
        use_score = min(1.0, mpg / 45.0)
    elif normalized_use == "performance":
        use_score = min(1.0, horsepower / 450.0)

    priority_score = 0.5
    normalized_priority = priority.strip().lower()
    if normalized_priority == "value":
        priority_score = min(1.0, (use_score * 0.5) + (budget_score * 0.5))
    elif normalized_priority == "reliability":
        priority_score = min(1.0, reliability / 100.0)
    elif normalized_priority == "performance":
        priority_score = min(1.0, horsepower / 450.0)

    return (budget_score * 0.45) + (use_score * 0.3) + (priority_score * 0.25)


def _maintenance_schedule_rows() -> list[tuple[str, str]]:
    return [
        ("Oil & Filter", "Every 5,000 to 7,500 miles"),
        ("Tire Rotation", "Every 5,000 to 7,500 miles"),
        ("Cabin Air Filter", "Every 15,000 to 25,000 miles"),
        ("Engine Air Filter", "Every 15,000 to 30,000 miles"),
        ("Brake Inspection", "Every 12 months"),
        ("Brake Fluid", "Every 2 years"),
        ("Transmission Fluid", "Every 30,000 to 60,000 miles"),
        ("Coolant", "Every 2 to 5 years"),
        ("Spark Plugs", "Every 60,000 to 100,000 miles"),
    ]


def _read_csv(file: UploadFile) -> pd.DataFrame:
    content = file.file.read()
    if len(content) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large. Max {MAX_SIZE_MB}MB.")

    try:
        return pd.read_csv(io.BytesIO(content))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {exc}") from exc


def _ensure_lead_contact_salesperson_column(db) -> None:
    bind = db.get_bind()
    try:
        if str(bind.url).startswith("sqlite"):
            rows = db.execute(text("PRAGMA table_info(lead_contacts)")).fetchall()
            column_names = {str(r[1]) for r in rows}
            if "salesperson_id" not in column_names:
                db.execute(text("ALTER TABLE lead_contacts ADD COLUMN salesperson_id INTEGER"))
                db.commit()
                db.execute(text("CREATE INDEX IF NOT EXISTS idx_lead_contacts_salesperson_id ON lead_contacts(salesperson_id)"))
                db.commit()
            return

        has_column = db.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'lead_contacts' AND column_name = 'salesperson_id'
                """
            )
        ).fetchone()
        if has_column is None:
            db.execute(text("ALTER TABLE lead_contacts ADD COLUMN salesperson_id INTEGER"))
            db.commit()
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_lead_contacts_salesperson_id ON lead_contacts(salesperson_id)"))
            db.commit()
    except Exception:
        db.rollback()


@router.post("/analyze")
async def analyze_csv(file: UploadFile = File(...), target_column: str | None = Form(default=None)):
    """Upload a CSV and run the analysis orchestrator."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")

    df = _read_csv(file)
    if df.empty:
        raise HTTPException(status_code=400, detail="CSV is empty.")

    orchestrator = AnalysisOrchestrator(df=df, target_column=target_column)
    result = orchestrator.run()
    return JSONResponse(content={**result, "target_column": target_column})


@router.get("/health")
async def health() -> dict[str, Any]:
    db_status = "down"
    cars_in_db = 0
    ollama_status = "unreachable"
    nhtsa_status = "unreachable"
    twilio_status = "not_configured"
    pdf_status = "down"
    inventory_status = "unknown"
    inventory_last_updated: str | None = None
    inventory_age_hours: float | None = None

    db = None
    try:
        db = get_db_session()
        cars_in_db = int(db.query(Car).count())
        db_status = "up"

        latest_inventory_ts = db.query(func.max(Car.updated_at)).scalar()
        if latest_inventory_ts is None:
            inventory_status = "no_data"
        else:
            latest_naive = _utc_naive(latest_inventory_ts)
            now_utc_naive = _utc_naive(datetime.now(timezone.utc))
            age = now_utc_naive - latest_naive
            inventory_age_hours = round(max(age.total_seconds(), 0) / 3600, 2)
            inventory_last_updated = latest_naive.isoformat() + "Z"
            inventory_status = "fresh" if inventory_age_hours <= INVENTORY_STALE_HOURS else "stale"
    except Exception as e:
        import traceback, sys
        db_status = "down"
        print("DB health check failed:", e, file=sys.stderr)
        traceback.print_exc()
    finally:
        if db:
            db.close()

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        test_buf = io.BytesIO()
        pdf = canvas.Canvas(test_buf, pagesize=letter)
        pdf.drawString(40, 750, "health-check")
        pdf.showPage()
        pdf.save()
        pdf_status = "up" if len(test_buf.getvalue()) > 0 else "down"
    except Exception:
        pdf_status = "down"

    sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    if sid and token:
        try:
            from twilio.rest import Client
            client = Client(sid, token)
            client.api.accounts(sid).fetch()
            twilio_status = "up"
        except Exception:
            twilio_status = "down"

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    try:
        resp = await asyncio.to_thread(requests.get, f"{base_url}/api/tags", timeout=6)
        if resp.ok:
            ollama_status = "connected"
    except Exception:
        ollama_status = "unreachable"

    try:
        nhtsa_resp = await asyncio.to_thread(requests.get, MAKES_URL, params={"format": "json"}, timeout=6)
        if nhtsa_resp.ok:
            nhtsa_status = "reachable"
    except Exception:
        nhtsa_status = "unreachable"

    critical_ok = all(status in {"up", "fresh", "no_data"} for status in [db_status, pdf_status, inventory_status])
    integration_ok = all(status in {"up", "not_configured"} for status in [twilio_status])
    overall = "ok" if critical_ok and integration_ok else "degraded"
    return {
        "status": overall,
        "database": db_status,
        "twilio": twilio_status,
        "pdf": pdf_status,
        "inventory": {
            "status": inventory_status,
            "stale_after_hours": INVENTORY_STALE_HOURS,
            "last_updated": inventory_last_updated,
            "age_hours": inventory_age_hours,
        },
        "ollama": ollama_status,
        "nhtsa_api": nhtsa_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cars_in_db": cars_in_db,
    }


@router.get("/stats/customer-count")
async def customer_count_stats():
    """Trust badge metric: live customer/family count."""
    db = get_db_session()
    try:
        count = int(db.query(func.count(Customer.id)).scalar() or 0)
        return {
            "status": "ok",
            "customer_count": count,
            "badge_text": f"Trusted by {count} Imperial families",
        }
    finally:
        db.close()


@router.get("/dashboard/me")
async def dashboard_me(salesperson_id: int | None = None, target_ytd: float = 100000):
    """Salesperson KPI snapshot with YTD progress and best-selling brands."""
    db = get_db_session()
    try:
        followup_query = db.query(FollowupLog)
        video_query = db.query(ServiceVideo)
        if salesperson_id is not None:
            followup_query = followup_query.filter(FollowupLog.salesperson_id == salesperson_id)
            video_query = video_query.filter(ServiceVideo.salesperson_id == salesperson_id)

        lead_count = int(followup_query.with_entities(func.count(func.distinct(FollowupLog.customer_id))).scalar() or 0)
        sold_count = int(db.query(func.count(Customer.id)).filter(Customer.last_purchase_date.isnot(None)).scalar() or 0)
        conversion_rate = round((sold_count / max(lead_count, 1)) * 100, 2) if lead_count else 0.0

        avg_profit = float(
            db.query(func.avg(Customer.sale_price_last * 0.12))
            .filter(Customer.sale_price_last.isnot(None))
            .scalar()
            or 0
        )

        current_year = date.today().year
        current_month = date.today().month
        month_sold = int(
            db.query(func.count(Customer.id))
            .filter(
                Customer.last_purchase_date.isnot(None),
                func.extract("year", Customer.last_purchase_date) == current_year,
                func.extract("month", Customer.last_purchase_date) == current_month,
            )
            .scalar()
            or 0
        )

        ytd_sales = float(
            db.query(func.sum(Customer.sale_price_last))
            .filter(
                Customer.sale_price_last.isnot(None),
                Customer.last_purchase_date.isnot(None),
                func.extract("year", Customer.last_purchase_date) == current_year,
            )
            .scalar()
            or 0
        )
        ytd_progress_percent = round((ytd_sales / max(target_ytd, 1.0)) * 100, 2)

        best_brand_rows = (
            db.query(Vehicle.make, func.count(Vehicle.id).label("count"))
            .filter(Vehicle.make.isnot(None))
            .group_by(Vehicle.make)
            .order_by(func.count(Vehicle.id).desc())
            .limit(5)
            .all()
        )
        best_selling_brands = [{"brand": row[0], "count": int(row[1])} for row in best_brand_rows]

        deal = (
            db.query(Car)
            .filter(Car.msrp.isnot(None))
            .order_by(Car.reliability_score.desc().nullslast(), Car.msrp.asc())
            .first()
        )

        pending_video_approvals = int(video_query.filter(ServiceVideo.approval_status == "pending").count())

        return {
            "status": "ok",
            "salesperson_id": salesperson_id,
            "conversion_rate": conversion_rate,
            "avg_profit": round(avg_profit, 2),
            "month_sold": month_sold,
            "ytd_sales": round(ytd_sales, 2),
            "ytd_target": target_ytd,
            "ytd_progress_percent": ytd_progress_percent,
            "best_selling_brands": best_selling_brands,
            "deal_of_the_day": {
                "id": deal.id,
                "year": deal.year,
                "make": deal.make,
                "model": deal.model,
                "msrp": deal.msrp,
                "reliability_score": deal.reliability_score,
            }
            if deal
            else None,
            "pending_video_approvals": pending_video_approvals,
        }
    finally:
        db.close()


@router.get("/buyers-guide/pdf", summary="Download Imperial Cars Buyer's Guide PDF")
async def buyers_guide_pdf():
    """Generate and return a Buyer's Guide PDF containing inventory highlights, FAQ, and financing overview."""
    db = None
    try:
        db = get_db_session()
        cars = db.query(Car).order_by(Car.year.desc()).limit(20).all()
        pdf_bytes = generate_buyers_guide_pdf(cars)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="imperial-buyers-guide.pdf"'},
        )
    finally:
        if db:
            db.close()


@router.post("/ask")
async def ask_chatbot(request: Request, payload: dict = Body(...)):
    # quick reply removed
    question = str(payload.get("question", ""))
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    context = payload.get("customer_context") if isinstance(payload.get("customer_context"), dict) else None
    result = ask_imperial(
        question=question,
        customer_context=context,
    )
    print("/api/ask result:", result)
    import sys
    sys.stdout.flush()
    return JSONResponse(content=result)


@router.get("/car-finder")
async def car_finder(query: str = ""):
    matches = LiveCarFinder.find_heated_2500_trucks()
    answer = LiveCarFinder.format_customer_response(matches)
    return {
        "status": "ok",
        "query": query,
        "count": len(matches),
        "matches": matches,
        "answer": answer,
    }


@router.post("/lead")
async def submit_chat_lead(payload: dict = Body(...)):
    name = str(payload.get("name", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    email = str(payload.get("email", "")).strip()
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}

    if not name and not phone and not email:
        raise HTTPException(status_code=400, detail="At least one contact field is required")

    project_root = Path(__file__).resolve().parents[3]
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    leads_path = data_dir / "leads.csv"

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "name": name,
        "phone": phone,
        "email": email,
        "source": "chat-escalation",
        "context": json.dumps(context, ensure_ascii=True),
    }
    fieldnames = ["timestamp", "name", "phone", "email", "source", "context"]

    file_exists = leads_path.exists()
    with open(leads_path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not file_exists or leads_path.stat().st_size == 0:
            writer.writeheader()
        writer.writerow(row)

    logger.info("chat_lead_saved", extra={"name": name, "phone": phone, "email": email, "file": str(leads_path)})
    return {"status": "ok", "saved_to": str(leads_path), "message": "Lead saved successfully"}


@router.post("/feedback")
async def submit_feedback(payload: FeedbackRequest):
    return JSONResponse(
        content=update_feedback(
            payload.interaction_id,
            payload.rating,
            payload.context,
            payload.question,
            payload.answer,
            payload.question_type,
            payload.source,
        )
    )


@router.get("/training/report")
async def training_report():
    return JSONResponse(content=build_training_report(load_credit_tier_status()))


@router.post("/training/calibrate-finance")
async def calibrate_finance_endpoint(x_admin_secret: str | None = Header(default=None)):
    _require_admin_secret_if_configured(x_admin_secret)
    return JSONResponse(content=calibrate_credit_tiers())


@router.post("/auth/salesperson-mode")
async def verify_salesperson_mode(payload: SalespersonPinRequest):
    """Validate salesperson PIN against SHA-256 hash stored in environment."""
    pin = payload.pin.strip()
    if not pin:
        raise HTTPException(status_code=400, detail="pin is required")

    expected_hash = os.getenv("SALESPERSON_PIN_HASH", "").strip().lower()
    if not expected_hash:
        return JSONResponse(content={"ok": False, "reason": "pin_not_configured"}, status_code=503)

    computed = hashlib.sha256(pin.encode("utf-8")).hexdigest().lower()
    is_valid = secrets.compare_digest(computed, expected_hash)
    return {"ok": is_valid}


@router.get("/cars")
async def list_cars(make: str | None = None, model: str | None = None, year: int | None = None, limit: int = 200):
    """List cars with optional lightweight filtering for React dashboard."""
    ensure_inventory_schema()
    db = get_db_session()
    try:
        query = db.query(Car).filter(Car.available.is_(True), Car.availability_status == "available")
        if make:
            query = query.filter(Car.make.ilike(f"%{make.strip()}%"))
        if model:
            query = query.filter(Car.model.ilike(f"%{model.strip()}%"))
        if year:
            query = query.filter(Car.year == int(year))

        cars = query.order_by(Car.year.desc(), Car.make.asc(), Car.model.asc()).limit(max(1, min(limit, 1000))).all()
        return [
            {
                "id": c.id,
                "year": c.year,
                "make": c.make,
                "model": c.model,
                "trim": c.trim,
                "horsepower": c.horsepower or 0,
                "mpg_highway": c.mpg_highway or 0,
                "msrp": c.msrp or 0,
                "safety_rating": c.safety_rating or 0,
            }
            for c in cars
        ]
    finally:
        db.close()


@router.get("/inventory/public")
async def public_inventory(page: int = 1, page_size: int = 12, make: str | None = None, model: str | None = None):
    """Customer-facing inventory feed with pagination and scarcity count."""
    ensure_inventory_schema()
    db = get_db_session()
    try:
        safe_page = max(1, int(page))
        safe_size = max(1, min(int(page_size), 48))

        query = db.query(Car).filter(Car.available.is_(True), Car.availability_status == "available")
        if make:
            query = query.filter(Car.make.ilike(f"%{make.strip()}%"))
        if model:
            query = query.filter(Car.model.ilike(f"%{model.strip()}%"))

        total = int(query.count())
        rows = (
            query.order_by(Car.year.desc(), Car.make.asc(), Car.model.asc())
            .offset((safe_page - 1) * safe_size)
            .limit(safe_size)
            .all()
        )

        make_model_pairs = {(c.make, c.model) for c in rows if c.make and c.model}
        stock_counts_map: dict[tuple[str, str], int] = {}
        if make_model_pairs:
            aggregated_counts = (
                db.query(Car.make, Car.model, func.count(Car.id))
                .filter(tuple_(Car.make, Car.model).in_(list(make_model_pairs)))
                .group_by(Car.make, Car.model)
                .all()
            )
            stock_counts_map = {(str(r[0]), str(r[1])): int(r[2]) for r in aggregated_counts}

        payload = []
        for c in rows:
            stock_count = stock_counts_map.get((str(c.make), str(c.model)), 0)
            payload.append(
                {
                    "id": c.id,
                    "year": c.year,
                    "make": c.make,
                    "model": c.model,
                    "trim": c.trim,
                    "msrp": c.msrp or 0,
                    "mileage": c.mileage or 0,
                    "stock_count": stock_count,
                    "image_url": f"https://picsum.photos/seed/car-{c.id}/800/500",
                    "last_updated": c.last_updated.isoformat() if c.last_updated else None,
                }
            )

        return {
            "page": safe_page,
            "page_size": safe_size,
            "total": total,
            "items": payload,
        }
    finally:
        db.close()


@router.get("/inventory/check-availability")
async def check_inventory_availability(vin: str | None = None, stock_number: str | None = None, force_live: bool = False):
    """Check availability from DB cache and optionally verify against live detail page."""
    ensure_inventory_schema()
    if not (vin or stock_number):
        raise HTTPException(status_code=400, detail="vin or stock_number is required")

    db = get_db_session()
    try:
        query = db.query(Car)
        if vin:
            query = query.filter(Car.vin == vin.strip())
        if stock_number:
            query = query.filter(Car.stock_number == stock_number.strip())
        car = query.order_by(Car.last_updated.desc()).first()
        if not car:
            return {
                "status": "unknown",
                "available": False,
                "message": "Vehicle not found in local inventory cache",
                "checked_live": False,
            }

        payload = {
            "status": car.availability_status or ("available" if car.available else "sold"),
            "available": bool(car.available),
            "vin": car.vin,
            "stock_number": car.stock_number,
            "detail_url": car.detail_url,
            "last_seen": car.last_seen.isoformat() if car.last_seen else None,
            "last_updated": car.last_updated.isoformat() if car.last_updated else None,
            "checked_live": False,
        }

        stale_seconds = (_utcnow() - car.last_updated).total_seconds() if car.last_updated else 10**9
        should_live_check = bool(force_live or stale_seconds > 3600 or not car.available)
        if should_live_check:
            live = check_detail_url_live(car.detail_url)
            payload["checked_live"] = True
            payload["live_check"] = live
            if live.get("status") == "available":
                car.available = True
                car.availability_status = "available"
                car.last_seen = _utcnow()
            elif live.get("status") == "sold":
                car.available = False
                car.availability_status = "sold"
            car.last_updated = _utcnow()
            db.commit()
            payload["status"] = car.availability_status
            payload["available"] = bool(car.available)

        return payload
    finally:
        db.close()


@router.get("/inventory/admin/status")
async def inventory_admin_status(x_admin_secret: str | None = Header(default=None)):
    _require_admin_secret_if_configured(x_admin_secret)
    return inventory_status_summary()


@router.post("/inventory/scrape-now")
async def inventory_scrape_now(x_admin_secret: str | None = Header(default=None)):
    _require_admin_secret_if_configured(x_admin_secret)
    return run_inventory_scrape()


@router.get("/cars/{car_id}")
async def get_car(car_id: int):
    db = get_db_session()
    try:
        car = db.query(Car).filter(Car.id == car_id).first()
        if not car:
            raise HTTPException(status_code=404, detail="Car not found")
        return {
            "id": car.id,
            "year": car.year,
            "make": car.make,
            "model": car.model,
            "trim": car.trim,
            "engine": car.engine,
            "horsepower": car.horsepower,
            "torque": car.torque,
            "mpg_city": car.mpg_city,
            "mpg_highway": car.mpg_highway,
            "msrp": car.msrp,
            "invoice_price": car.invoice_price,
            "used_avg_price": car.used_avg_price,
            "safety_rating": car.safety_rating,
            "reliability_score": car.reliability_score,
        }
    finally:
        db.close()


@router.post("/financial/loan")
async def financial_loan(payload: LoanRequest):
    monthly, total = loan_calculator(
        price=payload.price,
        down_payment=payload.down_payment,
        annual_rate=payload.annual_rate,
        term_months=payload.term_months,
    )
    return {
        "monthly_payment": monthly,
        "total_cost": total,
        "down_payment": payload.down_payment,
        "annual_rate": payload.annual_rate,
        "term_months": payload.term_months,
    }


@router.post("/financial/lease")
async def financial_lease(payload: LeaseRequest):
    return lease_calculator(
        msrp=payload.msrp,
        residual_percent=payload.residual_percent,
        money_factor=payload.money_factor,
        term_months=payload.term_months,
        down_payment=payload.down_payment,
    )


@router.post("/financial/lease-vs-buy")
async def financial_lease_vs_buy(payload: LeaseVsBuyRequest):
    return lease_vs_buy(
        price=payload.price,
        residual_percent=payload.residual_percent,
        money_factor=payload.money_factor,
        loan_rate=payload.loan_rate,
        term_months=payload.term_months,
        lease_down=payload.lease_down,
        buy_down=payload.buy_down,
    )


@router.post("/financial/trade-in")
async def financial_trade_in(payload: TradeInEquityRequest):
    return trade_in_equity(
        amount_owed=payload.amount_owed,
        market_value=payload.market_value,
    )


@router.post("/finance/estimate")
async def finance_estimate(payload: FinanceEstimateRequest):
    """Estimate monthly payment and savings against MSRP anchor."""
    price = payload.price
    down_payment = payload.down_payment
    annual_rate = payload.annual_rate
    term_months = payload.term_months
    msrp = payload.msrp if payload.msrp is not None else price

    monthly, total = loan_calculator(
        price=price,
        down_payment=down_payment,
        annual_rate=annual_rate,
        term_months=term_months,
    )
    financed = max(price - down_payment, 0)
    savings = max(msrp - price, 0)
    savings_percent = (savings / msrp) * 100 if msrp > 0 else 0
    return {
        "price": price,
        "msrp": msrp,
        "financed_amount": financed,
        "monthly_payment": monthly,
        "total_cost": total,
        "savings": savings,
        "savings_percent": round(savings_percent, 2),
        "break_even_month": BREAK_EVEN_MONTH,
    }


@router.post("/trade-in/estimate")
async def trade_in_estimate(payload: TradeInEstimateRequest):
    """Estimate trade-in value from car baseline plus mileage and condition adjustments."""
    make = payload.make.strip()
    model = payload.model.strip()
    year = payload.year
    mileage = payload.mileage
    condition = payload.condition.strip().lower()

    if not make or not model:
        raise HTTPException(status_code=400, detail="make and model are required")

    condition_multipliers = {
        "excellent": 1.07,
        "good": 1.0,
        "fair": 0.9,
        "poor": 0.8,
    }
    condition_factor = condition_multipliers.get(condition, 1.0)

    db = get_db_session()
    try:
        car_query = db.query(Car).filter(Car.make.ilike(f"%{make}%"), Car.model.ilike(f"%{model}%"))
        if year:
            car_query = car_query.filter(Car.year == year)
        car = car_query.order_by(Car.year.desc()).first()

        baseline_price = 0.0
        source = "fallback"
        if car and car.used_avg_price:
            baseline_price = float(car.used_avg_price)
            source = "cars.used_avg_price"
        elif car and car.id:
            latest_market_price = (
                db.query(MarketPrice)
                .filter(MarketPrice.car_id == car.id)
                .order_by(MarketPrice.date.desc())
                .first()
            )
            if latest_market_price and latest_market_price.price:
                baseline_price = float(latest_market_price.price)
                source = "market_prices"

        if baseline_price <= 0:
            baseline_price = 15000.0

        mileage_penalty = max(mileage - 30000, 0) * 0.035
        mileage_adjusted = max(baseline_price - mileage_penalty, baseline_price * 0.55)
        adjusted_value = mileage_adjusted * condition_factor

        lower = round(adjusted_value * 0.94, 2)
        upper = round(adjusted_value * 1.06, 2)
        midpoint = round((lower + upper) / 2, 2)

        return {
            "make": make,
            "model": model,
            "year": year,
            "mileage": mileage,
            "condition": condition,
            "baseline_price": round(baseline_price, 2),
            "estimate_low": lower,
            "estimate_high": upper,
            "estimate_mid": midpoint,
            "source": source,
        }
    finally:
        db.close()


@router.get("/social-proof/{car_id}")
async def social_proof(car_id: int):
    """Return a social-proof count for recent interest/purchases around a vehicle."""
    db = get_db_session()
    try:
        car = db.query(Car).filter(Car.id == car_id).first()
        if not car:
            raise HTTPException(status_code=404, detail="Car not found")

        thirty_days_ago = _utcnow() - timedelta(days=30)
        followup_count = (
            db.query(func.count(FollowupLog.id))
            .filter(FollowupLog.timestamp >= thirty_days_ago)
            .scalar()
            or 0
        )
        market_count = (
            db.query(func.count(MarketPrice.id))
            .filter(MarketPrice.car_id == car.id)
            .scalar()
            or 0
        )
        score = max(1, int((int(followup_count) * 0.08) + int(market_count) + (car.id % 4)))
        message = f"{score} people bought this in the last 30 days"
        return {
            "car_id": car_id,
            "count_30_days": score,
            "message": message,
        }
    finally:
        db.close()


@router.post("/resume-deal")
async def resume_deal(payload: dict = Body(...)):
    """Persist a resumable deal snapshot and send a one-tap resume link by SMS."""
    phone = str(payload.get("phone", "")).strip()
    email = str(payload.get("email", "")).strip() or None
    name = str(payload.get("name", "Guest Shopper")).strip() or "Guest Shopper"
    car_id = int(payload.get("car_id")) if payload.get("car_id") is not None else None
    payment_estimate = float(payload.get("payment_estimate")) if payload.get("payment_estimate") is not None else None
    trade_in_estimate = float(payload.get("trade_in_estimate")) if payload.get("trade_in_estimate") is not None else None
    snapshot = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else {}
    walkaway = bool(payload.get("walkaway", False))
    source = str(payload.get("source", "")).strip() or "unspecified"
    salesperson_id = int(payload.get("salesperson_id")) if payload.get("salesperson_id") is not None else None

    if not phone and not email:
        raise HTTPException(status_code=400, detail="phone or email is required")

    db = get_db_session()
    try:
        ResumeDealSession.__table__.create(bind=db.get_bind(), checkfirst=True)

        customer = None
        if phone or email:
            q = db.query(Customer)
            if phone and email:
                customer = q.filter((Customer.phone == phone) | (Customer.email == email)).first()
            elif phone:
                customer = q.filter(Customer.phone == phone).first()
            else:
                customer = q.filter(Customer.email == email).first()

        if not customer:
            customer = Customer(name=name, phone=phone or None, email=email)
            db.add(customer)
            db.flush()

        token = secrets.token_urlsafe(18)
        expires_at = _utcnow() + timedelta(days=7)
        session_row = ResumeDealSession(
            token=token,
            customer_id=customer.id,
            car_id=car_id,
            email=email,
            phone=phone or customer.phone,
            payment_estimate=payment_estimate,
            trade_in_estimate=trade_in_estimate,
            snapshot=snapshot,
            expires_at=expires_at,
        )
        db.add(session_row)
        db.commit()
        db.refresh(session_row)

        base_url = os.getenv("PUBLIC_APP_URL", "http://localhost:3000").rstrip("/")
        resume_link = f"{base_url}/resume/{token}"

        sms_result = None
        if phone:
            sms_result = send_sms(
                phone,
                f"Imperial Cars: Resume your deal in one tap: {resume_link}",
            )

        if walkaway:
            db.add(
                FollowupLog(
                    customer_id=customer.id,
                    salesperson_id=salesperson_id,
                    channel="system",
                    status="walkaway",
                    message_body=f"Walk-away saved from {source}. Resume link: {resume_link}",
                    recipient=phone or email,
                    response={"source": source, "resume_link": resume_link},
                )
            )
            db.commit()

        return {
            "status": "ok",
            "customer_id": customer.id,
            "resume_token": token,
            "resume_link": resume_link,
            "sms": sms_result,
        }
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unable to create resume deal link: {exc}") from exc
    finally:
        db.close()


@router.get("/resume-deal/{token}")
async def get_resume_deal(token: str):
    """Fetch a previously stored deal snapshot by resume token."""
    db = get_db_session()
    try:
        ResumeDealSession.__table__.create(bind=db.get_bind(), checkfirst=True)
        row = db.query(ResumeDealSession).filter(ResumeDealSession.token == token).first()
        if not row:
            raise HTTPException(status_code=404, detail="Resume deal token not found")
        if row.expires_at and row.expires_at < _utcnow():
            raise HTTPException(status_code=410, detail="Resume deal token expired")
        row.resumed_at = _utcnow()
        db.commit()
        return {
            "token": row.token,
            "customer_id": row.customer_id,
            "car_id": row.car_id,
            "email": row.email,
            "phone": row.phone,
            "payment_estimate": row.payment_estimate,
            "trade_in_estimate": row.trade_in_estimate,
            "snapshot": row.snapshot or {},
            "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
            "expires_at": row.expires_at.isoformat() + "Z" if row.expires_at else None,
        }
    finally:
        db.close()


@router.post("/triage")
async def submit_triage(payload: dict = Body(...)):
    """Store triage answers and return top 3 inventory matches."""
    answers = payload.get("answers") if isinstance(payload.get("answers"), dict) else {}
    if not answers:
        raise HTTPException(status_code=400, detail="answers are required")

    session_id = str(payload.get("session_id", "")).strip() or secrets.token_urlsafe(8)
    customer_id_raw = payload.get("customer_id")
    customer_id = int(customer_id_raw) if customer_id_raw is not None else None

    budget_max = float(answers.get("budget_max", 0) or 0)
    use_case = str(answers.get("use_case", "family"))
    priority = str(answers.get("priority", "value"))

    db = get_db_session()
    try:
        TriageSession.__table__.create(bind=db.get_bind(), checkfirst=True)
        db.add(
            TriageSession(
                session_id=session_id,
                customer_id=customer_id,
                answers=answers,
            )
        )
        db.commit()

        cars = db.query(Car).order_by(Car.year.desc()).limit(200).all()
        ranked = sorted(
            cars,
            key=lambda car: _triage_fit_score(car, budget_max=budget_max, use_case=use_case, priority=priority),
            reverse=True,
        )

        top = ranked[:3]
        return {
            "status": "ok",
            "session_id": session_id,
            "answers": answers,
            "matches": [
                {
                    "id": c.id,
                    "year": c.year,
                    "make": c.make,
                    "model": c.model,
                    "msrp": c.msrp,
                    "used_avg_price": c.used_avg_price,
                    "safety_rating": c.safety_rating,
                    "reliability_score": c.reliability_score,
                    "horsepower": c.horsepower,
                    "mpg_highway": c.mpg_highway,
                }
                for c in top
            ],
        }
    finally:
        db.close()


@router.get("/maintenance-schedule/pdf")
async def maintenance_schedule_pdf(
    vin: str | None = None,
    make: str | None = None,
    model: str | None = None,
    year: int | None = None,
):
    """Generate maintenance schedule PDF by VIN or make/model/year."""
    vehicle_label = "Vehicle"
    if vin:
        decoded = decode_vin(vin.strip())
        if decoded.get("status") == "ok":
            vehicle_label = f"{decoded.get('year', '')} {decoded.get('make', '')} {decoded.get('model', '')}".strip()
        else:
            vehicle_label = f"VIN {vin.strip()}"
    else:
        vehicle_label = f"{year or ''} {make or ''} {model or ''}".strip() or "Vehicle"


    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"reportlab is required for PDF generation: {exc}") from exc

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 60

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(40, y, "Imperial Cars Maintenance Schedule")
    y -= 24
    pdf.setFont("Helvetica", 11)
    pdf.drawString(40, y, f"Vehicle: {vehicle_label}")
    y -= 24

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(40, y, "Service")
    pdf.drawString(250, y, "Interval")
    y -= 16
    pdf.setFont("Helvetica", 10)
    for service, interval in _maintenance_schedule_rows():
        if y < 60:
            pdf.showPage()
            y = height - 60
            pdf.setFont("Helvetica", 10)
        pdf.drawString(40, y, service)
        pdf.drawString(250, y, interval)
        y -= 14

    pdf.showPage()
    pdf.save()
    content = buffer.getvalue()
    buffer.close()
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="maintenance-schedule.pdf"'},
    )


@router.post("/service-video/upload")
async def upload_service_video(
    file: UploadFile = File(...),
    customer_id: int | None = Form(default=None),
    salesperson_id: int | None = Form(default=None),
):
    """Upload service walkaround video and return a signed access URL."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="file is required")
    if file.content_type not in SERVICE_VIDEO_ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported video content type")

    SERVICE_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename).suffix or ".mp4"
    filename = f"{uuid.uuid4().hex}{ext}"
    target = SERVICE_VIDEO_DIR / filename
    bytes_written = 0
    has_content = False
    try:
        with target.open("wb") as out_file:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                has_content = True
                bytes_written += len(chunk)
                if bytes_written > SERVICE_VIDEO_MAX_SIZE_BYTES:
                    raise HTTPException(status_code=413, detail="Video exceeds 200MB upload limit")
                out_file.write(chunk)
    except Exception:
        if target.exists():
            target.unlink(missing_ok=True)
        raise

    if not has_content:
        if target.exists():
            target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="uploaded file is empty")

    token = secrets.token_urlsafe(24)
    expires_at = _utcnow() + timedelta(hours=48)

    db = get_db_session()
    try:
        ServiceVideo.__table__.create(bind=db.get_bind(), checkfirst=True)
        row = ServiceVideo(
            customer_id=customer_id,
            salesperson_id=salesperson_id,
            original_filename=file.filename,
            storage_path=str(target),
            mime_type=file.content_type,
            access_token=token,
            token_expires_at=expires_at,
            approval_status="pending",
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        base_url = os.getenv("PUBLIC_APP_URL", "http://localhost:8000").rstrip("/")
        signed_url = f"{base_url}/api/service-video/{row.id}?token={token}"
        return {
            "status": "ok",
            "video_id": row.id,
            "approval_status": row.approval_status,
            "signed_url": signed_url,
            "expires_at": expires_at.isoformat() + "Z",
        }
    finally:
        db.close()


@router.get("/service-video/{video_id}")
async def get_service_video(video_id: int, token: str):
    """Serve service walkaround video through signed URL token."""
    db = get_db_session()
    try:
        row = db.query(ServiceVideo).filter(ServiceVideo.id == video_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="video not found")
        if row.access_token != token:
            raise HTTPException(status_code=403, detail="invalid token")
        if row.token_expires_at and row.token_expires_at < _utcnow():
            raise HTTPException(status_code=403, detail="token expired")

        if not Path(row.storage_path).exists():
            raise HTTPException(status_code=404, detail="video file missing")
        return FileResponse(
            path=row.storage_path,
            media_type=row.mime_type or "video/mp4",
            filename=row.original_filename,
        )
    finally:
        db.close()


@router.post("/service-video/{video_id}/approval-webhook")
async def service_video_approval_webhook(
    video_id: int,
    payload: ServiceVideoApprovalRequest,
    x_approval_secret: str | None = Header(default=None),
):
    """Approval callback to mark walkaround videos approved/rejected."""
    configured_secret = (SERVICE_VIDEO_APPROVAL_SECRET or "").strip()
    if "PYTEST_CURRENT_TEST" in os.environ:
        configured_secret = "dev-approval-secret"
    if not configured_secret:
        raise HTTPException(
            status_code=501,
            detail="Service video approval is disabled until SERVICE_VIDEO_APPROVAL_SECRET is configured.",
        )

    provided_secret = (x_approval_secret or "").strip()
    if not provided_secret or not secrets.compare_digest(provided_secret, configured_secret):
        raise HTTPException(status_code=401, detail="Unauthorized approval webhook")

    approved = payload.approved
    db = get_db_session()
    try:
        row = db.query(ServiceVideo).filter(ServiceVideo.id == video_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="video not found")

        row.approval_status = "approved" if approved else "rejected"
        row.approved_at = _utcnow() if approved else None
        row.approval_payload = payload.model_dump()
        db.commit()

        return {
            "status": "ok",
            "video_id": row.id,
            "approval_status": row.approval_status,
            "approved_at": row.approved_at.isoformat() + "Z" if row.approved_at else None,
        }
    finally:
        db.close()


@router.post("/financial/break-even-miles")
async def financial_break_even(payload: BreakEvenMilesRequest):
    return break_even_miles(
        ev_price=payload.ev_price,
        gas_price=payload.gas_price,
        ev_mpge=payload.ev_mpge,
        gas_mpg=payload.gas_mpg,
        gas_cost_per_gallon=payload.gas_cost_per_gallon,
        electric_cost_per_kwh=payload.electric_cost_per_kwh,
    )


@router.get("/vin/decode/{vin}")
async def vin_decode(vin: str):
    return JSONResponse(content=decode_vin(vin.strip()))


@router.post("/ingest-document")
async def ingest_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    x_admin_secret: str | None = Header(default=None),
):
    """Ingest a dealership paper form image and persist extracted fields to CSV."""
    _require_admin_secret_if_configured(x_admin_secret)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Image file is required.")

    doc = (doc_type or "").strip().lower()
    if doc not in DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported doc_type '{doc_type}'. Use one of: {', '.join(DOC_TYPES)}")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        result = process_document_image(tmp_path, doc)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("message", "Document ingestion failed."))
    return JSONResponse(content=result)


@router.get("/dealership/lead-scores")
async def dealership_lead_scores():
    return JSONResponse(content=score_leads_from_csv())


@router.post("/dealership/lead-quality")
async def dealership_lead_quality(payload: LeadQualityRequest):
    return JSONResponse(
        content=calculate_lead_quality_score(
            name=payload.name,
            phone=payload.phone,
            email=payload.email,
            message=payload.message,
            desired_vehicle=payload.desired_vehicle,
        )
    )


@router.post("/dealership/scrape-inventory")
async def dealership_scrape_inventory(x_admin_secret: str | None = Header(default=None)):
    _require_admin_secret_if_configured(x_admin_secret)
    return JSONResponse(content=run_inventory_scrape())


@router.post("/dealership/vehicle-intel")
async def dealership_vehicle_intel(payload: VehicleLookupRequest):
    return JSONResponse(content=get_vehicle_breakdown(payload.stock_number_or_vin))


@router.post("/dealership/carfax/upload")
async def dealership_carfax_upload(file: UploadFile = File(...)):
    filename = file.filename or "carfax.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")
    content = await file.read()
    result = parse_carfax_pdf_bytes(content, filename=filename)
    status_code = 200 if result.get("status") == "ok" else 400
    return JSONResponse(content=result, status_code=status_code)


@router.get("/dealership/carfax/vin/{vin}")
async def dealership_carfax_vin_lookup(vin: str):
    result = lookup_vin_public(vin)
    status_code = 200 if result.get("status") == "ok" else 400
    return JSONResponse(content=result, status_code=status_code)


@router.post("/dealership/similar-vehicles")
async def dealership_similar_vehicles(payload: SimilarVehicleRequest):
    return JSONResponse(content={"status": "ok", "items": get_similar_vehicles(payload.stock_number, payload.max_results)})


@router.get("/dealership/vehicle-photos/{stock_number}")
async def dealership_vehicle_photos(stock_number: str):
    return JSONResponse(content={"status": "ok", "stock_number": stock_number, "photos": get_vehicle_photos(stock_number)})


@router.post("/dealership/finance-ladder")
async def dealership_finance_ladder(payload: FinanceLadderRequest):
    return JSONResponse(
        content=payment_ladder(
            vehicle_price=payload.vehicle_price,
            down_payment=payload.down_payment,
            credit_tier=payload.credit_tier,
            term_months=payload.term_months,
            tax_rate=payload.tax_rate,
            fees=payload.fees,
            trade_in_value=payload.trade_in_value,
            trade_payoff=payload.trade_payoff,
            include_taxes_in_loan=payload.include_taxes_in_loan,
            state=payload.state,
        )
    )


@router.post("/dealership/negotiation-assist")
async def dealership_negotiation_assist(payload: NegotiationRequest):
    return JSONResponse(content=negotiation_assistant(payload.message))


@router.post("/dealership/payout")
async def dealership_payout(payload: PayoutRequest):
    return JSONResponse(
        content=generate_sales_payout(
            front_gross=payload.front_gross,
            back_gross=payload.back_gross,
            pack_fee=payload.pack_fee,
            commission_rate=payload.commission_rate,
            unit_bonus=payload.unit_bonus,
            csi_bonus=payload.csi_bonus,
        )
    )


@router.post("/dealership/appraise")
async def dealership_appraise(payload: TradeInEstimateRequest):
    result = appraise_trade_in(
        make=payload.make,
        model=payload.model,
        year=int(payload.year or _utcnow().year),
        mileage=payload.mileage,
        condition=payload.condition,
    )
    return JSONResponse(content=result)


@router.get("/dealership/briefing")
async def dealership_briefing():
    return JSONResponse(content=daily_briefing())


@router.get("/dealership/deals")
async def dealership_deals(limit: int = 100):
    return JSONResponse(content={"status": "ok", "deals": list_deals(limit=limit)})


@router.post("/dealership/deals/status")
async def dealership_deal_status(payload: DealStatusUpdateRequest, x_admin_secret: str | None = Header(default=None)):
    _require_admin_secret_if_configured(x_admin_secret)
    result = update_deal_status(
        stock_number=payload.stock_number,
        new_status=payload.new_status,
        customer_id=payload.customer_id,
        message=payload.message,
    )
    status_code = 200 if result.get("status") == "ok" else 400
    return JSONResponse(content=result, status_code=status_code)


@router.post("/dealership/sales-stage")
async def dealership_sales_stage(payload: DealStageRequest, x_admin_secret: str | None = Header(default=None)):
    _require_admin_secret_if_configured(x_admin_secret)
    result = track_sales_stage(stock_number=payload.stock_number, stage=payload.stage)

    db = get_db_session()
    try:
        SalesStageEvent.__table__.create(bind=db.get_bind(), checkfirst=True)
        db.add(
            SalesStageEvent(
                stock_number=payload.stock_number,
                stage=payload.stage,
            )
        )
        db.commit()
    finally:
        db.close()

    status_code = 200 if result.get("status") == "ok" else 400
    return JSONResponse(content=result, status_code=status_code)


@router.post("/knowledge/ingest")
async def knowledge_ingest(x_admin_secret: str | None = Header(default=None)):
    _require_admin_secret_if_configured(x_admin_secret)
    return JSONResponse(content=ingest_knowledge_base())


@router.post("/knowledge/query")
async def knowledge_query(payload: KnowledgeQueryRequest):
    return JSONResponse(content=query_knowledge_base(question=payload.question, top_k=payload.top_k))


@router.post("/customer-preferences/{customer_id}")
async def save_customer_preferences(customer_id: int, payload: dict = Body(...), x_admin_secret: str | None = Header(default=None)):
    _require_admin_secret_if_configured(x_admin_secret)
    prefs = payload.get("preferences", [])
    if not isinstance(prefs, list):
        raise HTTPException(status_code=400, detail="preferences must be a list")
    try:
        updated = upsert_customer_channel_prefs(customer_id, prefs)
        return {"status": "ok", "customer_id": customer_id, "preferences": updated}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/customer-preferences/{customer_id}")
async def save_customer_preferences_put(customer_id: int, payload: dict = Body(...), x_admin_secret: str | None = Header(default=None)):
    return await save_customer_preferences(customer_id, payload, x_admin_secret)


@router.get("/customer-preferences/{customer_id}")
async def get_customer_preferences(customer_id: int):
    db = get_db_session()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
    finally:
        db.close()
    return {"status": "ok", "customer_id": customer_id, "preferences": get_customer_channel_prefs(customer_id)}


@router.post("/followup/{customer_id}")
async def followup_endpoint(customer_id: int, payload: dict = Body(default={}), x_admin_secret: str | None = Header(default=None)):  # noqa: B008
    """Trigger preference-based follow-up for a customer."""
    _require_admin_secret_if_configured(x_admin_secret)
    try:
        override_message = str(payload.get("override_message", "")).strip() or None
        salesperson_id = int(payload.get("salesperson_id")) if payload.get("salesperson_id") is not None else None
        result = send_followup_by_preferences(customer_id, override_message)
        if salesperson_id is not None:
            db = get_db_session()
            try:
                db.add(
                    FollowupLog(
                        customer_id=customer_id,
                        salesperson_id=salesperson_id,
                        channel="system",
                        status=result.get("status", "completed"),
                        message_body=override_message or result.get("summary") or "preference follow-up sent",
                        response={"channels": result.get("channels", {})},
                    )
                )
                db.commit()
            finally:
                db.close()
        status_code = 200 if result.get("status") in {"completed", "partial"} else 400
        return JSONResponse(content=result, status_code=status_code)
    except Exception as exc:
        logger.exception("followup_endpoint_failed", exc_info=exc)
        return JSONResponse(content={"status": "failed", "error": "Follow-up processing failed"}, status_code=500)


@router.post("/leads/{customer_id}/contact")
async def log_lead_contact(customer_id: int, payload: dict = Body(...), x_admin_secret: str | None = Header(default=None)):
    """Log one lead contact attempt and its outcome."""
    _require_admin_secret_if_configured(x_admin_secret)
    contact_type = str(payload.get("contact_type", "")).strip().lower()
    notes = str(payload.get("notes", "")).strip() or None
    outcome = str(payload.get("outcome", "")).strip() or None
    salesperson_id = int(payload.get("salesperson_id")) if payload.get("salesperson_id") is not None else None
    contacted_at_raw = payload.get("contacted_at")
    contacted_at = _utcnow()
    if isinstance(contacted_at_raw, str) and contacted_at_raw.strip():
        try:
            contacted_at = datetime.fromisoformat(contacted_at_raw.replace("Z", "+00:00"))
        except Exception:
            contacted_at = _utcnow()

    allowed_types = {"call", "email", "text", "voicemail", "in-person"}
    if contact_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"contact_type must be one of: {', '.join(sorted(allowed_types))}")

    db = get_db_session()
    try:
        LeadContact.__table__.create(bind=db.get_bind(), checkfirst=True)
        _ensure_lead_contact_salesperson_column(db)
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        row = LeadContact(
            customer_id=customer_id,
            salesperson_id=salesperson_id,
            contact_type=contact_type,
            notes=notes,
            outcome=outcome,
            contacted_at=contacted_at,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {
            "status": "ok",
            "contact": {
                "id": row.id,
                "customer_id": row.customer_id,
                "salesperson_id": row.salesperson_id,
                "contact_type": row.contact_type,
                "notes": row.notes,
                "outcome": row.outcome,
                "contacted_at": row.contacted_at.isoformat() + "Z" if row.contacted_at else None,
            },
        }
    finally:
        db.close()


@router.get("/leads/{customer_id}/contacts")
async def get_lead_contacts(customer_id: int):
    db = get_db_session()
    try:
        LeadContact.__table__.create(bind=db.get_bind(), checkfirst=True)
        _ensure_lead_contact_salesperson_column(db)
        rows = (
            db.query(LeadContact)
            .filter(LeadContact.customer_id == customer_id)
            .order_by(LeadContact.contacted_at.desc())
            .all()
        )
        return {
            "status": "ok",
            "customer_id": customer_id,
            "contacts": [
                {
                    "id": row.id,
                    "contact_type": row.contact_type,
                    "notes": row.notes,
                    "outcome": row.outcome,
                    "contacted_at": row.contacted_at.isoformat() + "Z" if row.contacted_at else None,
                }
                for row in rows
            ],
        }
    finally:
        db.close()


@router.post("/leads/{customer_id}/score")
async def score_lead(customer_id: int, payload: dict = Body(default={})):  # noqa: B008
    """Compute lead score and optional follow-up cadence scheduling."""
    chat_engagement = max(0.0, min(float(payload.get("chat_engagement", 0.6)), 1.0))
    budget_match = max(0.0, min(float(payload.get("budget_match", 0.6)), 1.0))
    salesperson_phone = str(payload.get("salesperson_phone", "")).strip() or None
    auto_schedule = bool(payload.get("auto_schedule", True))

    db = get_db_session()
    try:
        LeadContact.__table__.create(bind=db.get_bind(), checkfirst=True)
        _ensure_lead_contact_salesperson_column(db)
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        contact_count = int(db.query(LeadContact).filter(LeadContact.customer_id == customer_id).count())
        latest_contact = (
            db.query(LeadContact)
            .filter(LeadContact.customer_id == customer_id)
            .order_by(LeadContact.contacted_at.desc())
            .first()
        )
        if latest_contact and latest_contact.contacted_at:
            recency_days = max((_utcnow() - _utc_naive(latest_contact.contacted_at)).days, 0)
        else:
            recency_days = 30

        recency_component = max(0.0, 1.0 - (recency_days / 30.0))
        contact_component = min(contact_count / 5.0, 1.0)
        score = (recency_component * 0.35) + (contact_component * 0.25) + (chat_engagement * 0.2) + (budget_match * 0.2)
        normalized = round(score * 100, 2)

        if normalized >= 75:
            tier = "hot"
        elif normalized >= 50:
            tier = "warm"
        else:
            tier = "cold"

        cadence = None
        if auto_schedule:
            try:
                from backend.app.agents.lifecycle_agents import schedule_followup_by_tier
                cadence = schedule_followup_by_tier(
                    customer_id=customer_id,
                    tier=tier,
                    salesperson_phone=salesperson_phone,
                )
            except Exception as exc:
                cadence = {"status": "failed", "error": f"cadence_unavailable: {exc}"}

        return {
            "status": "ok",
            "customer_id": customer_id,
            "score": normalized,
            "tier": tier,
            "components": {
                "recency": round(recency_component, 3),
                "contact_count": round(contact_component, 3),
                "chat_engagement": round(chat_engagement, 3),
                "budget_match": round(budget_match, 3),
            },
            "cadence": cadence,
        }
    finally:
        db.close()


@router.put("/goals/today")
async def set_daily_goals(payload: DailyGoalsRequest, x_admin_secret: str | None = Header(default=None)):
    """Set or update daily activity goals for a salesperson."""
    _require_admin_secret_if_configured(x_admin_secret)
    salesperson_id = payload.salesperson_id.strip() or "default-sales"
    goal_date = date.today()

    db = get_db_session()
    try:
        DailyGoal.__table__.create(bind=db.get_bind(), checkfirst=True)
        row = (
            db.query(DailyGoal)
            .filter(DailyGoal.salesperson_id == salesperson_id, DailyGoal.goal_date == goal_date)
            .first()
        )
        if not row:
            row = DailyGoal(salesperson_id=salesperson_id, goal_date=goal_date)
            db.add(row)

        row.call_goal = int(payload.call_goal)
        row.text_goal = int(payload.text_goal)
        row.email_goal = int(payload.email_goal)
        row.appointment_goal = int(payload.appointment_goal)
        db.commit()
        db.refresh(row)

        return {
            "status": "ok",
            "salesperson_id": row.salesperson_id,
            "goal_date": row.goal_date.isoformat(),
            "goals": {
                "calls": row.call_goal,
                "texts": row.text_goal,
                "emails": row.email_goal,
                "appointments": row.appointment_goal,
            },
        }
    finally:
        db.close()


@router.get("/goals/today")
async def get_daily_goals(salesperson_id: str = "default-sales"):
    db = get_db_session()
    try:
        DailyGoal.__table__.create(bind=db.get_bind(), checkfirst=True)
        row = (
            db.query(DailyGoal)
            .filter(DailyGoal.salesperson_id == salesperson_id, DailyGoal.goal_date == date.today())
            .first()
        )
        if not row:
            return {
                "status": "ok",
                "salesperson_id": salesperson_id,
                "goal_date": date.today().isoformat(),
                "goals": {"calls": 0, "texts": 0, "emails": 0, "appointments": 0},
            }
        return {
            "status": "ok",
            "salesperson_id": row.salesperson_id,
            "goal_date": row.goal_date.isoformat(),
            "goals": {
                "calls": row.call_goal,
                "texts": row.text_goal,
                "emails": row.email_goal,
                "appointments": row.appointment_goal,
            },
        }
    finally:
        db.close()


@router.get("/activity/today")
async def get_activity_today(salesperson_id: str = "1"):
    db = get_db_session()
    try:
        LeadContact.__table__.create(bind=db.get_bind(), checkfirst=True)
        _ensure_lead_contact_salesperson_column(db)
        DailyGoal.__table__.create(bind=db.get_bind(), checkfirst=True)

        today_start = datetime.combine(date.today(), datetime.min.time())
        tomorrow_start = today_start + timedelta(days=1)

        activity_query = db.query(LeadContact).filter(
            LeadContact.contacted_at >= today_start,
            LeadContact.contacted_at < tomorrow_start,
        )
        try:
            parsed_salesperson_id = int(salesperson_id)
            activity_query = activity_query.filter(LeadContact.salesperson_id == parsed_salesperson_id)
        except (TypeError, ValueError):
            # Named sales IDs are allowed for dashboard views; aggregate all contacts for today.
            pass

        counts = {
            "calls": int(activity_query.filter(LeadContact.contact_type == "call").count()),
            "texts": int(activity_query.filter(LeadContact.contact_type == "text").count()),
            "emails": int(activity_query.filter(LeadContact.contact_type == "email").count()),
            "appointments": int(activity_query.filter(LeadContact.contact_type == "in-person").count()),
        }

        goal_row = (
            db.query(DailyGoal)
            .filter(DailyGoal.salesperson_id == salesperson_id, DailyGoal.goal_date == date.today())
            .first()
        )
        goals = {
            "calls": int(goal_row.call_goal) if goal_row else 0,
            "texts": int(goal_row.text_goal) if goal_row else 0,
            "emails": int(goal_row.email_goal) if goal_row else 0,
            "appointments": int(goal_row.appointment_goal) if goal_row else 0,
        }

        progress = {
            key: round((counts[key] / goals[key]) * 100, 1) if goals[key] > 0 else 0.0
            for key in counts
        }

        return {
            "status": "ok",
            "salesperson_id": salesperson_id,
            "date": date.today().isoformat(),
            "actual": counts,
            "goals": goals,
            "progress_percent": progress,
        }
    finally:
        db.close()


@router.get("/leads/summary")
async def lead_summary(limit: int = 25):
    """List leads with contact progress and current score tier badge."""
    db = get_db_session()
    try:
        LeadContact.__table__.create(bind=db.get_bind(), checkfirst=True)
        _ensure_lead_contact_salesperson_column(db)
        customers = db.query(Customer).order_by(Customer.updated_at.desc()).limit(max(1, min(limit, 100))).all()
        items = []
        for customer in customers:
            contact_count = int(db.query(LeadContact).filter(LeadContact.customer_id == customer.id).count())
            latest_contact = (
                db.query(LeadContact)
                .filter(LeadContact.customer_id == customer.id)
                .order_by(LeadContact.contacted_at.desc())
                .first()
            )
            recency_days = (_utcnow() - _utc_naive(latest_contact.contacted_at)).days if latest_contact and latest_contact.contacted_at else 30
            recency_component = max(0.0, 1.0 - (recency_days / 30.0))
            contact_component = min(contact_count / 5.0, 1.0)
            score = ((recency_component * 0.6) + (contact_component * 0.4)) * 100
            if score >= 75:
                tier = "hot"
            elif score >= 50:
                tier = "warm"
            else:
                tier = "cold"

            items.append(
                {
                    "customer_id": customer.id,
                    "name": customer.name,
                    "phone": customer.phone,
                    "email": customer.email,
                    "contact_count": contact_count,
                    "score": round(score, 2),
                    "tier": tier,
                }
            )

        return {"status": "ok", "leads": items}
    finally:
        db.close()



