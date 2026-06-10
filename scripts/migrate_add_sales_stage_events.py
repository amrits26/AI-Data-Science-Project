#!/usr/bin/env python
"""Add sales_stage_events table for auditable stage transition tracking."""

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
from backend.app.database.models import SalesStageEvent  # noqa: E402


def run() -> int:
    print("=" * 72)
    print("MIGRATION: add sales_stage_events table")
    print("=" * 72)

    with engine.begin() as conn:
        SalesStageEvent.__table__.create(bind=conn, checkfirst=True)
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sales_stage_stock_created ON sales_stage_events(stock_number, created_at)"))

    print("Migration completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
