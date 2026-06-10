#!/usr/bin/env python
"""Phase 5 migration: add salesperson columns and service_videos table."""

from __future__ import annotations

import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.app.core.platform_compat import patch_platform_machine_for_windows

patch_platform_machine_for_windows()

from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv(os.path.join(project_root, ".env"))

from backend.app.database import engine  # noqa: E402
from backend.app.database.models import ServiceVideo  # noqa: E402


def _is_sqlite() -> bool:
    return str(engine.url).startswith("sqlite")


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    if _is_sqlite():
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return any(str(r[1]) == column_name for r in rows)

    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table_name AND column_name = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).fetchone()
    return row is not None


def run() -> int:
    print("=" * 72)
    print("PHASE 5 MIGRATION: salesperson fields + service_videos")
    print("=" * 72)

    with engine.begin() as conn:
        if not _column_exists(conn, "followup_log", "salesperson_id"):
            conn.execute(text("ALTER TABLE followup_log ADD COLUMN salesperson_id INTEGER"))

        if not _column_exists(conn, "service_jobs", "salesperson_id"):
            conn.execute(text("ALTER TABLE service_jobs ADD COLUMN salesperson_id INTEGER"))

        ServiceVideo.__table__.create(bind=conn, checkfirst=True)

        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_followup_log_salesperson_id ON followup_log(salesperson_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_service_jobs_salesperson_id ON service_jobs(salesperson_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_service_videos_customer_id ON service_videos(customer_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_service_videos_salesperson_id ON service_videos(salesperson_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_service_videos_access_token ON service_videos(access_token)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_service_videos_approval_status ON service_videos(approval_status)"))

    print("Migration completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
