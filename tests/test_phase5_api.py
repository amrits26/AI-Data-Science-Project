from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.agents.lifecycle_agents import run_review_request_workflow
from backend.app.database import Base, Customer, NurtureLog, ServiceVideo, engine, get_db_session
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
            db.query(NurtureLog).filter(NurtureLog.customer_id.in_(customer_ids)).delete(synchronize_session=False)
            videos = db.query(ServiceVideo).filter(ServiceVideo.customer_id.in_(customer_ids)).all()
            for video in videos:
                path = Path(video.storage_path)
                if path.exists():
                    path.unlink(missing_ok=True)
            db.query(ServiceVideo).filter(ServiceVideo.customer_id.in_(customer_ids)).delete(synchronize_session=False)
            db.query(Customer).filter(Customer.id.in_(customer_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_review_request_workflow_triggers_at_48_hours() -> None:
    _ensure_tables()
    prefix = f"P5TEST-{uuid4().hex[:8]}"

    db = get_db_session()
    try:
        customer = Customer(name=f"{prefix}-Buyer", phone="+15550001111", last_purchase_date=date(2026, 5, 18))
        db.add(customer)
        db.commit()
        customer_id = int(customer.id)
    finally:
        db.close()

    try:
        run_review_request_workflow(reference_date=date(2026, 5, 20))
        db2 = get_db_session()
        try:
            log = (
                db2.query(NurtureLog)
                .filter(NurtureLog.customer_id == customer_id, NurtureLog.message_type == "review_request_48h")
                .first()
            )
            assert log is not None
        finally:
            db2.close()
    finally:
        _cleanup_prefix(prefix)


def test_service_video_upload_and_approval_flow() -> None:
    _ensure_tables()
    prefix = f"P5TEST-{uuid4().hex[:8]}"

    db = get_db_session()
    try:
        customer = Customer(name=f"{prefix}-Owner", email=f"{prefix}@example.com")
        db.add(customer)
        db.commit()
        customer_id = int(customer.id)
    finally:
        db.close()

    client = _client()
    try:
        upload = client.post(
            "/api/service-video/upload",
            files={"file": ("walkaround.mp4", b"fake-video-bytes", "video/mp4")},
            data={"customer_id": str(customer_id), "salesperson_id": "1"},
        )
        assert upload.status_code == 200
        payload = upload.json()
        assert payload["status"] == "ok"
        video_id = int(payload["video_id"])

        approve = client.post(
            f"/api/service-video/{video_id}/approval-webhook",
            json={"approved": True, "reviewer": "test"},
            headers={"x-approval-secret": "dev-approval-secret"},
        )
        assert approve.status_code == 200
        assert approve.json()["approval_status"] == "approved"
    finally:
        _cleanup_prefix(prefix)
