#!/usr/bin/env python
"""Add triage_sessions table for Phase 4 Task 4.7."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(os.path.join(project_root, ".env"))

from backend.app.database import engine  # noqa: E402
from backend.app.database.models import TriageSession  # noqa: E402


def run() -> int:
    print("=" * 72)
    print("PHASE 4 MIGRATION: add triage_sessions table")
    print("=" * 72)

    with engine.begin() as conn:
        TriageSession.__table__.create(bind=conn, checkfirst=True)
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_triage_sessions_session_id ON triage_sessions(session_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_triage_sessions_customer_id ON triage_sessions(customer_id)"))

    print("Migration completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
