#!/usr/bin/env python
"""Add daily_goals table for Phase 3 Task 3.4."""

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
from backend.app.database.models import DailyGoal, SessionSnapshot  # noqa: E402


def run() -> int:
    print("=" * 72)
    print("PHASE 3 MIGRATION: add daily_goals and session_snapshots tables")
    print("=" * 72)

    with engine.begin() as conn:
        DailyGoal.__table__.create(bind=conn, checkfirst=True)
        SessionSnapshot.__table__.create(bind=conn, checkfirst=True)
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_daily_goals_salesperson_date ON daily_goals(salesperson_id, goal_date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_session_snapshots_session_id ON session_snapshots(session_id)"))

    print("Migration completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
