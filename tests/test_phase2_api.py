from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.database import (
    Base,
    Car,
    Customer,
    FollowupLog,
    MarketPrice,
    ResumeDealSession,
    engine,
    get_db_session,
)
from backend.app.main import app


def _client() -> TestClient:
    return TestClient(app, base_url="http://localhost")


def _ensure_tables() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _cleanup_prefix(prefix: str) -> None:
    db = get_db_session()
    try:
        cars = db.query(Car).filter(Car.make.like(f"{prefix}%")).all()
        car_ids = [c.id for c in cars]

        if car_ids:
            db.query(MarketPrice).filter(MarketPrice.car_id.in_(car_ids)).delete(synchronize_session=False)

        db.query(FollowupLog).filter(FollowupLog.message_body.like(f"{prefix}%")).delete(synchronize_session=False)
        db.query(ResumeDealSession).filter(ResumeDealSession.email.like(f"{prefix}%")).delete(synchronize_session=False)
        db.query(Customer).filter(Customer.name.like(f"{prefix}%")).delete(synchronize_session=False)

        if car_ids:
            db.query(Car).filter(Car.id.in_(car_ids)).delete(synchronize_session=False)

        db.commit()
    finally:
        db.close()


def test_finance_estimate_endpoint_returns_expected_shape_and_value() -> None:
    _ensure_tables()
    client = _client()

    resp = client.post(
        "/api/finance/estimate",
        json={
            "price": 25000,
            "down_payment": 0,
            "annual_rate": 5,
            "term_months": 60,
            "msrp": 28000,
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["monthly_payment"] == 471.78
    assert payload["total_cost"] > payload["price"]
    assert payload["savings"] == 3000.0
    assert payload["break_even_month"] == 48


def test_trade_in_estimate_uses_market_data_and_returns_range() -> None:
    _ensure_tables()
    prefix = f"P2TEST-{uuid4().hex[:8]}"

    db = get_db_session()
    try:
        car = Car(
            make=f"{prefix}-MAKE",
            model=f"{prefix}-MODEL",
            year=2021,
            used_avg_price=20000,
            msrp=28000,
        )
        db.add(car)
        db.commit()
        db.refresh(car)
    finally:
        db.close()

    try:
        client = _client()
        resp = client.post(
            "/api/trade-in/estimate",
            json={
                "year": 2021,
                "make": f"{prefix}-MAKE",
                "model": f"{prefix}-MODEL",
                "mileage": 42000,
                "condition": "good",
            },
        )

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["source"] in {"cars.used_avg_price", "market_prices", "fallback"}
        assert payload["estimate_low"] < payload["estimate_high"]
        assert payload["estimate_low"] <= payload["estimate_mid"] <= payload["estimate_high"]
    finally:
        _cleanup_prefix(prefix)


def test_social_proof_endpoint_returns_recent_count_message() -> None:
    _ensure_tables()
    prefix = f"P2TEST-{uuid4().hex[:8]}"

    db = get_db_session()
    try:
        customer = Customer(name=f"{prefix}-Customer", email=f"{prefix}@example.com", phone="+15551230001")
        db.add(customer)
        db.flush()

        car = Car(make=f"{prefix}-MAKE", model=f"{prefix}-MODEL", year=2022, used_avg_price=23000)
        db.add(car)
        db.flush()

        db.add(MarketPrice(car_id=car.id, price=22000))
        db.add(
            FollowupLog(
                customer_id=customer.id,
                channel="sms",
                status="sent",
                message_body=f"{prefix} follow-up message",
                recipient=customer.phone,
                timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        db.commit()
        car_id = car.id
    finally:
        db.close()

    try:
        client = _client()
        resp = client.get(f"/api/social-proof/{car_id}")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["car_id"] == car_id
        assert payload["count_30_days"] >= 1
        assert "30 days" in payload["message"]
    finally:
        _cleanup_prefix(prefix)


def test_resume_deal_creates_snapshot_and_token() -> None:
    _ensure_tables()
    prefix = f"P2TEST-{uuid4().hex[:8]}"

    client = _client()
    resp = client.post(
        "/api/resume-deal",
        json={
            "name": f"{prefix}-Lead",
            "email": f"{prefix}@example.com",
            "phone": "5551234567",
            "payment_estimate": 472,
            "trade_in_estimate": 12000,
            "snapshot": {"phase": "2", "source": prefix},
        },
    )

    try:
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "ok"
        assert payload["resume_token"]
        assert "/resume/" in payload["resume_link"]

        db = get_db_session()
        try:
            row = db.query(ResumeDealSession).filter(ResumeDealSession.token == payload["resume_token"]).first()
            assert row is not None
            assert row.snapshot is not None
            assert row.snapshot.get("source") == prefix
        finally:
            db.close()
    finally:
        _cleanup_prefix(prefix)
