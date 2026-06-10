from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend.app.database import Base, SalesStageEvent, engine, get_db_session
from backend.app.main import app
from backend.app.api import routes


def _client() -> TestClient:
    return TestClient(app, base_url="http://localhost")


def test_phase6_health_endpoint_shape() -> None:
    client = _client()
    resp = client.get("/api/health")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["status"] in {"ok", "degraded"}
    assert payload["database"] in {"up", "down"}
    assert payload["twilio"] in {"up", "down", "not_configured"}
    assert payload["pdf"] in {"up", "down"}
    assert isinstance(payload["inventory"], dict)
    assert payload["inventory"]["status"] in {"fresh", "stale", "no_data", "unknown"}
    assert "timestamp" in payload
    assert "cars_in_db" in payload


def test_phase6_dashboard_and_maintenance_endpoints() -> None:
    client = _client()

    dashboard = client.get("/api/dashboard/me")
    assert dashboard.status_code == 200
    assert dashboard.json().get("status") == "ok"

    schedule = client.get("/api/maintenance-schedule/pdf", params={"make": "Toyota", "model": "Camry", "year": 2022})
    assert schedule.status_code == 200
    assert schedule.headers.get("content-type", "").startswith("application/pdf")
    assert len(schedule.content) > 200


def test_phase6_sales_stage_logs_event(tmp_path: Path) -> None:
    Base.metadata.create_all(bind=engine)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame([
        {"stock_number": "STAGE-001", "status": "open"},
    ]).to_csv(data_dir / "deals.csv", index=False)

    old_data_dir = os.environ.get("DATA_DIR")
    os.environ["DATA_DIR"] = str(data_dir)

    try:
        client = _client()
        resp = client.post("/api/dealership/sales-stage", json={"stock_number": "STAGE-001", "stage": "negotiation"})
        assert resp.status_code == 200

        db = get_db_session()
        try:
            row = (
                db.query(SalesStageEvent)
                .filter(SalesStageEvent.stock_number == "STAGE-001", SalesStageEvent.stage == "negotiation")
                .order_by(SalesStageEvent.id.desc())
                .first()
            )
            assert row is not None
        finally:
            db.close()
    finally:
        if old_data_dir is None:
            os.environ.pop("DATA_DIR", None)
        else:
            os.environ["DATA_DIR"] = old_data_dir


def test_phase6_admin_secret_guard_when_configured() -> None:
    old_secret = routes.ADMIN_API_SECRET
    routes.ADMIN_API_SECRET = "test-admin-secret"

    try:
        client = _client()

        unauthorized = client.post(
            "/api/dealership/deals/status",
            json={"stock_number": "NOPE", "new_status": "open"},
        )
        assert unauthorized.status_code == 401

        authorized = client.post(
            "/api/dealership/deals/status",
            headers={"x-admin-secret": "test-admin-secret"},
            json={"stock_number": "NOPE", "new_status": "open"},
        )
        assert authorized.status_code in {200, 400}
    finally:
        routes.ADMIN_API_SECRET = old_secret
