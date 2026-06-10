from __future__ import annotations

from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.agents.imperial_chatbot import _detect_conflict_mode, _detect_customer_role
from backend.app.agents.lifecycle_agents import run_service_heart_workflow
from backend.app.database import Base, Car, Customer, FollowupLog, NurtureLog, ResumeDealSession, TriageSession, engine, get_db_session
from backend.app.main import app


def _client() -> TestClient:
    return TestClient(app, base_url="http://localhost")


def _ensure_tables() -> None:
    Base.metadata.create_all(bind=engine)


def _cleanup_prefix(prefix: str) -> None:
    db = get_db_session()
    try:
        cars = db.query(Car).filter(Car.make.like(f"{prefix}%")).all()
        car_ids = [c.id for c in cars]

        customers = db.query(Customer).filter(Customer.name.like(f"{prefix}%")).all()
        customer_ids = [c.id for c in customers]

        if customer_ids:
            db.query(FollowupLog).filter(FollowupLog.customer_id.in_(customer_ids)).delete(synchronize_session=False)
            db.query(ResumeDealSession).filter(ResumeDealSession.customer_id.in_(customer_ids)).delete(synchronize_session=False)

        db.query(TriageSession).filter(TriageSession.session_id.like(f"{prefix}%")).delete(synchronize_session=False)

        if car_ids:
            db.query(Car).filter(Car.id.in_(car_ids)).delete(synchronize_session=False)
        if customer_ids:
            db.query(Customer).filter(Customer.id.in_(customer_ids)).delete(synchronize_session=False)

        db.commit()
    finally:
        db.close()


def test_role_detector_and_conflict_mode() -> None:
    role, tone = _detect_customer_role("Can you show me APR and monthly payment options?")
    assert role == "finance"
    assert tone == "analytical"

    conflict = _detect_conflict_mode("This is too expensive and out of my budget")
    assert conflict["triggered"] is True
    assert len(conflict["options"]) == 3


def test_trust_badge_customer_count_endpoint() -> None:
    _ensure_tables()
    client = _client()
    resp = client.get("/api/stats/customer-count")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert isinstance(payload["customer_count"], int)
    assert "Trusted by" in payload["badge_text"]


def test_triage_endpoint_stores_answers_and_returns_top_matches() -> None:
    _ensure_tables()
    prefix = f"P4TEST-{uuid4().hex[:8]}"

    db = get_db_session()
    try:
        db.add_all(
            [
                Car(make=f"{prefix}-Toyota", model="Camry", year=2022, msrp=30000, reliability_score=86, safety_rating=5, mpg_highway=39, horsepower=203),
                Car(make=f"{prefix}-Honda", model="Accord", year=2022, msrp=32000, reliability_score=84, safety_rating=5, mpg_highway=38, horsepower=192),
                Car(make=f"{prefix}-Ford", model="Mustang", year=2022, msrp=45000, reliability_score=74, safety_rating=4, mpg_highway=30, horsepower=450),
            ]
        )
        db.commit()
    finally:
        db.close()

    try:
        client = _client()
        session_id = f"{prefix}-session"
        resp = client.post(
            "/api/triage",
            json={
                "session_id": session_id,
                "answers": {
                    "budget_max": 35000,
                    "use_case": "family",
                    "priority": "reliability",
                },
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "ok"
        assert payload["session_id"] == session_id
        assert len(payload["matches"]) == 3

        db2 = get_db_session()
        try:
            stored = db2.query(TriageSession).filter(TriageSession.session_id == session_id).first()
            assert stored is not None
            assert stored.answers is not None
            assert int(stored.answers.get("budget_max", 0)) == 35000
        finally:
            db2.close()
    finally:
        _cleanup_prefix(prefix)


def test_walkaway_resume_logs_followup_entry() -> None:
    _ensure_tables()
    prefix = f"P4TEST-{uuid4().hex[:8]}"
    client = _client()

    try:
        resp = client.post(
            "/api/resume-deal",
            json={
                "name": f"{prefix}-Lead",
                "phone": "5551239988",
                "email": f"{prefix}@example.com",
                "walkaway": True,
                "source": "chatbot",
                "snapshot": {"phase": 4},
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "ok"

        db = get_db_session()
        try:
            customer = db.query(Customer).filter(Customer.email == f"{prefix}@example.com").first()
            assert customer is not None
            row = (
                db.query(FollowupLog)
                .filter(FollowupLog.customer_id == customer.id, FollowupLog.status == "walkaway")
                .first()
            )
            assert row is not None
            assert "Walk-away" in (row.message_body or "")
        finally:
            db.close()
    finally:
        _cleanup_prefix(prefix)


def test_service_heart_workflow_creates_30_day_message() -> None:
    _ensure_tables()
    prefix = f"P4TEST-{uuid4().hex[:8]}"

    db = get_db_session()
    try:
        customer = Customer(name=f"{prefix}-Customer", email=f"{prefix}@example.com")
        customer.last_purchase_date = date(2026, 4, 20)
        db.add(customer)
        db.commit()
    finally:
        db.close()

    try:
        run_service_heart_workflow(reference_date=date(2026, 5, 20))

        db2 = get_db_session()
        try:
            customer = db2.query(Customer).filter(Customer.email == f"{prefix}@example.com").first()
            assert customer is not None
            row = db2.query(FollowupLog).filter(FollowupLog.customer_id == customer.id).first()
            assert row is None
            heart = (
                db2.query(NurtureLog)
                .filter(NurtureLog.customer_id == customer.id, NurtureLog.message_type == "service_heart_30")
                .first()
            )
            assert heart is not None
        finally:
            db2.close()
    finally:
        _cleanup_prefix(prefix)
