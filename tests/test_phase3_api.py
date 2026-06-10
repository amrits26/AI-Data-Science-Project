from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.database import Base, Customer, DailyGoal, FollowupLog, LeadContact, engine, get_db_session
from backend.app.main import app


def _client() -> TestClient:
    return TestClient(app, base_url="http://localhost")


def _ensure_tables() -> None:
    Base.metadata.create_all(bind=engine)


def _cleanup_prefix(prefix: str) -> None:
    db = get_db_session()
    try:
        customers = db.query(Customer).filter(Customer.name.like(f"{prefix}%")).all()
        customer_ids = [c.id for c in customers]

        if customer_ids:
            db.query(LeadContact).filter(LeadContact.customer_id.in_(customer_ids)).delete(synchronize_session=False)
            db.query(FollowupLog).filter(FollowupLog.customer_id.in_(customer_ids)).delete(synchronize_session=False)

        db.query(DailyGoal).filter(DailyGoal.salesperson_id.like(f"{prefix}%")).delete(synchronize_session=False)

        if customer_ids:
            db.query(Customer).filter(Customer.id.in_(customer_ids)).delete(synchronize_session=False)

        db.commit()
    finally:
        db.close()


def _create_customer(prefix: str) -> int:
    db = get_db_session()
    try:
        customer = Customer(name=f"{prefix}-Lead", email=f"{prefix}@example.com", phone="+15550001111")
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return int(customer.id)
    finally:
        db.close()


def test_log_and_list_lead_contacts() -> None:
    _ensure_tables()
    prefix = f"P3TEST-{uuid4().hex[:8]}"
    customer_id = _create_customer(prefix)

    try:
        client = _client()
        create_resp = client.post(
            f"/api/leads/{customer_id}/contact",
            json={"contact_type": "call", "notes": "Initial outreach", "outcome": "connected"},
        )
        assert create_resp.status_code == 200
        assert create_resp.json()["contact"]["contact_type"] == "call"

        list_resp = client.get(f"/api/leads/{customer_id}/contacts")
        assert list_resp.status_code == 200
        payload = list_resp.json()
        assert payload["customer_id"] == customer_id
        assert len(payload["contacts"]) >= 1
        assert payload["contacts"][0]["contact_type"] == "call"
    finally:
        _cleanup_prefix(prefix)


def test_score_lead_returns_tier_and_cadence_metadata() -> None:
    _ensure_tables()
    prefix = f"P3TEST-{uuid4().hex[:8]}"
    customer_id = _create_customer(prefix)

    try:
        client = _client()
        client.post(
            f"/api/leads/{customer_id}/contact",
            json={"contact_type": "text", "notes": "Budget discussion", "outcome": "engaged"},
        )

        resp = client.post(
            f"/api/leads/{customer_id}/score",
            json={"chat_engagement": 0.95, "budget_match": 0.9, "auto_schedule": True},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["score"] >= 0
        assert payload["tier"] in {"hot", "warm", "cold"}
        assert payload["components"]["chat_engagement"] == 0.95
        assert payload["cadence"] is not None
        assert payload["cadence"]["status"] in {"ok", "failed"}
    finally:
        _cleanup_prefix(prefix)


def test_set_get_daily_goals_and_activity_snapshot() -> None:
    _ensure_tables()
    prefix = f"P3TEST-{uuid4().hex[:8]}"
    customer_id = _create_customer(prefix)
    salesperson_id = f"{prefix}-sales"

    try:
        client = _client()
        set_resp = client.put(
            "/api/goals/today",
            json={
                "salesperson_id": salesperson_id,
                "call_goal": 5,
                "text_goal": 6,
                "email_goal": 4,
                "appointment_goal": 2,
            },
        )
        assert set_resp.status_code == 200
        assert set_resp.json()["goals"]["calls"] == 5

        get_resp = client.get("/api/goals/today", params={"salesperson_id": salesperson_id})
        assert get_resp.status_code == 200
        assert get_resp.json()["goals"]["appointments"] == 2

        client.post(f"/api/leads/{customer_id}/contact", json={"contact_type": "call", "outcome": "completed"})
        client.post(f"/api/leads/{customer_id}/contact", json={"contact_type": "text", "outcome": "completed"})

        activity_resp = client.get("/api/activity/today", params={"salesperson_id": salesperson_id})
        assert activity_resp.status_code == 200
        activity = activity_resp.json()
        assert activity["actual"]["calls"] >= 1
        assert activity["actual"]["texts"] >= 1
        assert "progress_percent" in activity
    finally:
        _cleanup_prefix(prefix)
